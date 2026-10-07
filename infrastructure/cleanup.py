"""
cleanup.py
==========
Remove EVERYTHING the NovaMart project created in the AWS account, in
dependency order, so the account is back to its pre-project state:

  1. Bedrock Knowledge Bases (+ data sources). IAM roles are preserved unless
     they belong to the named CloudFormation stack, avoiding shared-role damage.
  2. The AgentCore CLI stack that holds the AgentCore Runtime
     (AgentCore-udacity-default, created by `agentcore deploy`) and its workload
     identity, plus Memory and the optional Gateway. The shared CDK bootstrap
     stack (CDKToolkit) is left in place.
  3. Bedrock Guardrail (all versions)
  4. S3 policy bucket contents (all object versions + delete markers)
  5. The CloudFormation stack (DynamoDB tables, S3 bucket, S3 Vectors bucket +
     indexes, IAM execution role, log group) - waits for DELETE_COMPLETE
  6. Exact AgentCore runtime log groups left outside the stacks. The script
     deliberately avoids broad prefix sweeps when ownership cannot be proven.
  7. Optionally (--disable-transaction-search) turn CloudWatch Transaction Search
     back off and remove the X-Ray resource policy

Usage (from the project root, same credentials/region as the project):

    python infrastructure/cleanup.py            # dry run - prints what would be deleted
    python infrastructure/cleanup.py --yes --confirm-project udacity-agentcore --confirm-account <account-id>

Region and names come from config.py / .env exactly as the project uses them.
Every step tolerates "already gone" and permission errors and keeps going, so
the script can be re-run until it reports nothing left.
"""

import argparse
import hashlib
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

REGION  = config.AWS_REGION
PREFIX  = config.PROJECT_NAME                     # udacity-agentcore
TS_POLICY_NAME = 'NovaMartTransactionSearchXRayAccess'
GATEWAY_ROLE_POLICY = 'InvokeConfiguredNovaMartFunctions'
GATEWAY_TRUST_POLICY = {
    'Version': '2012-10-17',
    'Statement': [{
        'Effect': 'Allow',
        'Principal': {'Service': 'bedrock-agentcore.amazonaws.com'},
        'Action': 'sts:AssumeRole',
    }],
}

DRY = True
FOUND = 0


def say(msg):
    print(f"  {msg}")


def act(label, fn):
    """Run one delete step unless dry-run; never abort the whole cleanup."""
    global FOUND
    FOUND += 1
    if DRY:
        say(f"[would delete] {label}")
        return True
    try:
        fn()
        say(f"[deleted] {label}")
        return True
    except ClientError as exc:
        code = exc.response.get('Error', {}).get('Code', '')
        if code in ('ResourceNotFoundException', 'NoSuchEntity', 'NoSuchBucket',
                    'NotFoundException', 'ValidationError'):
            say(f"[already gone] {label}")
        else:
            say(f"[FAILED] {label}: {code} {exc.response.get('Error', {}).get('Message', '')}")
        return False
    except Exception as exc:                                    # noqa: BLE001
        say(f"[FAILED] {label}: {exc}")
        return False


def safe(fn, default):
    try:
        return fn()
    except Exception:                                           # noqa: BLE001
        return default


# ─────────────────────────── 1. Knowledge Bases ───────────────────────────

def cleanup_knowledge_bases():
    print("\n1. Bedrock Knowledge Bases")
    agent = boto3.client('bedrock-agent', region_name=REGION)
    wanted_ids = {v for v in (config.RETURNS_KB_ID, config.SHIPPING_KB_ID, config.WARRANTY_KB_ID) if v}
    wanted_names = {
        f'{PREFIX}-returns-kb',
        f'{PREFIX}-shipping-kb',
        f'{PREFIX}-warranty-kb',
    }
    kbs = []
    for page in safe(lambda: list(agent.get_paginator('list_knowledge_bases').paginate()), []):
        for kb in page.get('knowledgeBaseSummaries', []):
            if kb['knowledgeBaseId'] in wanted_ids or kb['name'] in wanted_names:
                kbs.append(kb)
    if not kbs:
        say("none found")
        return
    for kb in kbs:
        kb_id = kb['knowledgeBaseId']
        for ds in safe(lambda: agent.list_data_sources(knowledgeBaseId=kb_id)['dataSourceSummaries'], []):
            act(f"data source {ds['name']} ({ds['dataSourceId']}) of KB {kb['name']}",
                lambda ds=ds: agent.delete_data_source(knowledgeBaseId=kb_id, dataSourceId=ds['dataSourceId']))
        act(f"knowledge base {kb['name']} ({kb_id})",
            lambda kb_id=kb_id: agent.delete_knowledge_base(knowledgeBaseId=kb_id))
    # Wait for the KBs to disappear before the stack removes vector indexes.
    if not DRY:
        deadline = time.time() + 180
        while time.time() < deadline:
            left = [kb for kb in kbs if safe(lambda kb=kb: agent.get_knowledge_base(
                knowledgeBaseId=kb['knowledgeBaseId']) and True, False)]
            if not left:
                break
            time.sleep(5)
# ─────────────────────────── 2. AgentCore ───────────────────────────

def wait_for_stack_gone(cf, name, timeout=900):
    print("  waiting for DELETE_COMPLETE", end='', flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            st = cf.describe_stacks(StackName=name)['Stacks'][0]['StackStatus']
        except ClientError:
            print(' done.')
            return
        if st == 'DELETE_FAILED':
            print(' DELETE_FAILED')
            for ev in cf.describe_stack_events(StackName=name)['StackEvents'][:20]:
                if ev.get('ResourceStatus') == 'DELETE_FAILED':
                    say(f"    {ev['LogicalResourceId']}: {ev.get('ResourceStatusReason', '')}")
            raise RuntimeError("stack deletion failed - see reasons above; fix and re-run")
        print('.', end='', flush=True)
        time.sleep(10)
    raise TimeoutError("stack still deleting after 15 min")


def cleanup_agentcore():
    print("\n2. AgentCore runtime (AgentCore CLI stack), memory, workload identity, gateway")
    ctl = boto3.client('bedrock-agentcore-control', region_name=REGION)
    cf  = boto3.client('cloudformation', region_name=REGION)
    runtime_ids = [rt['agentRuntimeId']
                   for rt in safe(lambda: ctl.list_agent_runtimes().get('agentRuntimes', []), [])
                   if rt['agentRuntimeName'] == config.AGENTCORE_RUNTIME_NAME]

    # The runtime was created by `agentcore deploy` (AgentCore CLI) as a CDK /
    # CloudFormation stack - delete the stack so CloudFormation removes the
    # runtime cleanly, then remove anything with the runtime name left behind.
    cli_stack = config.AGENTCORE_STACK_NAME
    try:
        status = cf.describe_stacks(StackName=cli_stack)['Stacks'][0]['StackStatus']
        say(f"stack {cli_stack} is {status}")

        def _delete_cli_stack():
            cf.delete_stack(StackName=cli_stack)
            wait_for_stack_gone(cf, cli_stack)
            # forget the deployment locally so a later `agentcore deploy` starts clean
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
            import agentcore_cli
            agentcore_cli.reset_deployed_state()
        act(f"AgentCore CLI stack {cli_stack} (runtime {config.AGENTCORE_RUNTIME_NAME})", _delete_cli_stack)
    except ClientError:
        say(f"stack {cli_stack} does not exist (nothing deployed with the AgentCore CLI)")

    for rt in safe(lambda: ctl.list_agent_runtimes().get('agentRuntimes', []), []):
        if rt['agentRuntimeName'] == config.AGENTCORE_RUNTIME_NAME:
            act(f"agent runtime {rt['agentRuntimeName']} ({rt['agentRuntimeId']}) left outside the stack",
                lambda rid=rt['agentRuntimeId']: ctl.delete_agent_runtime(agentRuntimeId=rid))
    for m in safe(lambda: ctl.list_memories().get('memories', []), []):
        if _is_project_memory(ctl, m['id']):
            act(f"memory {m['id']}", lambda mid=m['id']: ctl.delete_memory(memoryId=mid))
    # Workload identities are owned by the AgentCore CLI stack. Do not perform
    # a secondary name/substring sweep: an imprecise match could delete a
    # different runtime's identity.
    gateway_roles = set()
    gateway_names = _project_gateway_names(cf)
    for gw in safe(lambda: ctl.list_gateways().get('items', []), []):
        if gw['name'] in gateway_names:
            gid = gw['gatewayId']
            detail = safe(lambda gid=gid: ctl.get_gateway(gatewayIdentifier=gid), {})
            suffix = gw['name'].removeprefix('novamart-support-')
            expected_role = f'novamart-gateway-{suffix}'
            actual_role = detail.get('roleArn', '').split('/')[-1]
            if actual_role == expected_role:
                gateway_roles.add(actual_role)
            elif actual_role:
                say(f"[kept] gateway role {actual_role} (does not match {expected_role})")
            for t in safe(lambda: ctl.list_gateway_targets(gatewayIdentifier=gid).get('items', []), []):
                act(f"gateway target {t['name']}",
                    lambda t=t: ctl.delete_gateway_target(gatewayIdentifier=gid, targetId=t['targetId']))
            act(f"gateway {gw['name']}", lambda gid=gid: ctl.delete_gateway(gatewayIdentifier=gid))
    iam = boto3.client('iam')
    for role_name in sorted(gateway_roles):
        policy_present = _gateway_role_cleanup_state(iam, role_name)
        if policy_present is None:
            say(f"[kept] gateway role {role_name} (ownership or policy set is unexpected)")
            continue
        if policy_present:
            act(f"inline policy {GATEWAY_ROLE_POLICY} of {role_name}",
                lambda role_name=role_name: iam.delete_role_policy(
                    RoleName=role_name, PolicyName=GATEWAY_ROLE_POLICY))
        act(f"gateway role {role_name}",
            lambda role_name=role_name: iam.delete_role(RoleName=role_name))
    if not runtime_ids:
        say("no runtime named " + config.AGENTCORE_RUNTIME_NAME)
    return runtime_ids


def _project_gateway_names(cf):
    """Return only gateway names attributable to the configured project stack."""
    names = {f'novamart-support-{PREFIX}'}
    try:
        stack_id = cf.describe_stacks(StackName=PREFIX)['Stacks'][0]['StackId']
        stack_uuid = stack_id.split('/')[-1].split('-')[0]
        names.add(f'novamart-support-{stack_uuid}')
    except Exception:  # noqa: BLE001 - a missing stack must narrow, not widen, cleanup
        pass
    return names


def _is_project_memory(agentcore, memory_id):
    """Match the exact memory configuration created by configure_memory()."""
    if not memory_id.startswith(config.MEMORY_NAME):
        return False
    memory = safe(lambda: agentcore.get_memory(memoryId=memory_id)['memory'], {})
    strategies = memory.get('strategies', [])
    return (
        memory.get('id') == memory_id
        and memory.get('name') == config.MEMORY_NAME
        and memory.get('description') == 'Seven-day session summaries for NovaMart customer support.'
        and memory.get('eventExpiryDuration') == 7
        and any(
            strategy.get('type') == 'SUMMARIZATION'
            and strategy.get('name') == 'SessionSummary'
            and strategy.get('namespaces') == ['/summaries/{actorId}/{sessionId}']
            for strategy in strategies
        )
    )


def _gateway_role_cleanup_state(iam, role_name):
    """Return policy presence for an owned role, or None when ownership is uncertain."""
    try:
        role = iam.get_role(RoleName=role_name)['Role']
        tags = {tag['Key']: tag['Value'] for tag in role.get('Tags', [])}
        inline = set(iam.list_role_policies(RoleName=role_name)['PolicyNames'])
        attached = iam.list_attached_role_policies(RoleName=role_name)['AttachedPolicies']
    except Exception:  # noqa: BLE001 - uncertainty means preserve the role
        return None
    target_digest = tags.get('TargetDigest', '')
    if (
        role.get('AssumeRolePolicyDocument') != GATEWAY_TRUST_POLICY
        or set(tags) != {'ManagedBy', 'Project', 'TargetDigest'}
        or tags.get('ManagedBy') != 'NovaMart'
        or tags.get('Project') != PREFIX
        or len(target_digest) != 64
        or not inline <= {GATEWAY_ROLE_POLICY}
        or attached
    ):
        return None
    if not inline:
        return False
    try:
        policy = iam.get_role_policy(
            RoleName=role_name,
            PolicyName=GATEWAY_ROLE_POLICY,
        )['PolicyDocument']
    except Exception:  # noqa: BLE001 - uncertainty means preserve the role
        return None
    statements = policy.get('Statement', [])
    if not isinstance(statements, list):
        statements = [statements]
    if len(statements) != 1:
        return None
    statement = statements[0]
    resources = statement.get('Resource', [])
    if isinstance(resources, str):
        resources = [resources]
    valid_resources = bool(resources) and all(_is_concrete_lambda_arn(resource)
                                              for resource in resources)
    resource_digest = hashlib.sha256(
        '\n'.join(sorted(set(resources))).encode('utf-8')
    ).hexdigest()
    if (
        statement.get('Effect') != 'Allow'
        or statement.get('Action') != 'lambda:InvokeFunction'
        or not valid_resources
        or resource_digest != target_digest
        or set(statement) != {'Effect', 'Action', 'Resource'}
    ):
        return None
    return True


def _is_concrete_lambda_arn(resource):
    if not isinstance(resource, str) or '*' in resource:
        return False
    parts = resource.split(':', 6)
    return (
        len(parts) == 7
        and parts[0] == 'arn'
        and parts[1] in {'aws', 'aws-cn', 'aws-us-gov'}
        and parts[2] == 'lambda'
        and parts[5] == 'function'
        and bool(parts[6])
    )


# ─────────────────────────── 3. Guardrail ───────────────────────────

def cleanup_guardrail():
    print("\n3. Bedrock Guardrail")
    bedrock = boto3.client('bedrock', region_name=REGION)
    found = False
    for g in safe(lambda: bedrock.list_guardrails().get('guardrails', []), []):
        if g['name'] == config.GUARDRAIL_NAME:
            found = True
            act(f"guardrail {g['name']} ({g['id']}) incl. all versions",
                lambda gid=g['id']: bedrock.delete_guardrail(guardrailIdentifier=gid))
    if not found:
        say("none found")


# ─────────────────────────── 4./6. S3 + S3 Vectors ───────────────────────────

def empty_bucket(s3, bucket):
    """Delete every object version and delete marker (bucket is versioned)."""
    paginator = s3.get_paginator('list_object_versions')
    for page in paginator.paginate(Bucket=bucket):
        objs = [{'Key': o['Key'], 'VersionId': o['VersionId']}
                for key in ('Versions', 'DeleteMarkers') for o in page.get(key, [])]
        for i in range(0, len(objs), 1000):
            s3.delete_objects(Bucket=bucket, Delete={'Objects': objs[i:i + 1000], 'Quiet': True})


def _stack_physical_resource(logical_id):
    cf = boto3.client('cloudformation', region_name=REGION)
    return safe(
        lambda: cf.describe_stack_resource(
            StackName=PREFIX,
            LogicalResourceId=logical_id,
        )['StackResourceDetail']['PhysicalResourceId'],
        '',
    )


def project_buckets(_s3):
    bucket = _stack_physical_resource('PolicyDocumentsBucket')
    return [bucket] if bucket else []


def cleanup_bucket_contents():
    print("\n4. S3 policy bucket contents")
    s3 = boto3.client('s3', region_name=REGION)
    names = project_buckets(s3)
    if not names:
        say("none found")
    for b in names:
        act(f"all objects/versions in s3://{b}", lambda b=b: empty_bucket(s3, b))


def cleanup_vector_buckets():
    s3v = boto3.client('s3vectors', region_name=REGION)
    expected_name = _stack_physical_resource('VectorStoreBucket')
    if not expected_name:
        say("vector bucket not resolved from the configured stack; kept")
        return
    for vb in safe(lambda: s3v.list_vector_buckets().get('vectorBuckets', []), []):
        name = vb['vectorBucketName']
        if name != expected_name:
            continue
        for idx in safe(lambda: s3v.list_indexes(vectorBucketName=name).get('indexes', []), []):
            act(f"vector index {idx['indexName']} in {name}",
                lambda n=idx['indexName']: s3v.delete_index(vectorBucketName=name, indexName=n))
        act(f"vector bucket {name}", lambda name=name: s3v.delete_vector_bucket(vectorBucketName=name))


# ─────────────────────────── 5. CloudFormation ───────────────────────────

def cleanup_stack():
    print("\n5. CloudFormation stack")
    cf = boto3.client('cloudformation', region_name=REGION)
    try:
        status = cf.describe_stacks(StackName=PREFIX)['Stacks'][0]['StackStatus']
    except ClientError:
        say(f"stack {PREFIX} does not exist")
        return
    say(f"stack {PREFIX} is {status}")

    def _delete():
        cf.delete_stack(StackName=PREFIX)
        wait_for_stack_gone(cf, PREFIX)
    act(f"stack {PREFIX} (tables, buckets, vector bucket + indexes, role, log group)", _delete)


# ─────────────────────────── 6. leftovers ───────────────────────────

def cleanup_leftovers(runtime_ids):
    print("\n6. Exact AgentCore log-group leftovers")
    logs = boto3.client('logs', region_name=REGION)
    prefixes = [f"/aws/bedrock/agentcore/{PREFIX}"] + \
               [f"/aws/bedrock-agentcore/runtimes/{rid}" for rid in runtime_ids]
    for p in prefixes:
        for g in safe(lambda: logs.describe_log_groups(logGroupNamePrefix=p)['logGroups'], []):
            if g['logGroupName'] == p:
                act(f"log group {p}",
                    lambda p=p: logs.delete_log_group(logGroupName=p))


# ─────────────────────────── 7. Transaction Search (optional) ───────────────────────────

def disable_transaction_search():
    print("\n7. CloudWatch Transaction Search")
    xray = boto3.client('xray', region_name=REGION)
    logs = boto3.client('logs', region_name=REGION)
    dest = safe(lambda: xray.get_trace_segment_destination(), {})
    if dest.get('Destination') == 'CloudWatchLogs':
        act("trace segment destination -> XRay (Transaction Search off)",
            lambda: xray.update_trace_segment_destination(Destination='XRay'))
    else:
        say("Transaction Search already off")
    for pol in safe(lambda: logs.describe_resource_policies()['resourcePolicies'], []):
        if pol['policyName'] == TS_POLICY_NAME:
            act(f"CloudWatch Logs resource policy {TS_POLICY_NAME}",
                lambda: logs.delete_resource_policy(policyName=TS_POLICY_NAME))
    for g in ('aws/spans', '/aws/application-signals/data'):
        for lg in safe(lambda: logs.describe_log_groups(logGroupNamePrefix=g)['logGroups'], []):
            if lg['logGroupName'] == g:
                act(f"log group {g}", lambda g=g: logs.delete_log_group(logGroupName=g))


# ─────────────────────────── main ───────────────────────────

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Delete every AWS resource the NovaMart project created.")
    ap.add_argument('--yes', action='store_true', help='actually delete (default: dry run)')
    ap.add_argument('--confirm-project', metavar='PROJECT_NAME',
                    help='required with --yes; must exactly match the configured project name')
    ap.add_argument('--confirm-account', metavar='AWS_ACCOUNT_ID',
                    help='required with --yes; must exactly match the active AWS account')
    ap.add_argument('--disable-transaction-search', action='store_true',
                    help='also switch CloudWatch Transaction Search off and remove its resource policy')
    args = ap.parse_args()
    DRY = not args.yes

    ident = boto3.client('sts', region_name=REGION).get_caller_identity()
    if args.yes and args.confirm_project != PREFIX:
        ap.error(f"--yes requires --confirm-project {PREFIX}")
    if args.yes and args.confirm_account != ident['Account']:
        ap.error("--yes requires --confirm-account matching the active AWS account")
    print(f"{'DRY RUN - ' if DRY else ''}Cleaning up project '{PREFIX}' in {REGION} "
          f"as {ident['Arn']} (account {ident['Account']})")

    cleanup_knowledge_bases()
    runtime_ids = cleanup_agentcore()
    cleanup_guardrail()
    cleanup_bucket_contents()
    cleanup_vector_buckets()
    cleanup_stack()
    cleanup_leftovers(runtime_ids)
    if args.disable_transaction_search:
        disable_transaction_search()

    print()
    if DRY:
        print(f"{FOUND} deletion(s) planned. Re-run with --yes to execute.")
    else:
        print("Cleanup finished. Re-run once more to confirm nothing is left "
              "(AgentCore/KB deletions are asynchronous). Then clear the IDs in .env.")
