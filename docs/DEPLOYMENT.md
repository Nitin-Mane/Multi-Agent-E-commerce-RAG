# Deployment Guide

This guide describes the deployment sequence without embedding account-specific values. Commands assume PowerShell and an active Python virtual environment.

## 1. Confirm the target account

Use the Udacity AWS sandbox first when completing the course. If it is unavailable or lacks a required entitlement, use a personal account only with the account owner's approval and active cost monitoring.

```powershell
aws sts get-caller-identity
aws configure get region
```

Read the returned account and ARN carefully before provisioning anything.

## 2. Prepare local configuration

```powershell
Copy-Item .env.example .env
Copy-Item agentcore\agentcore.example.json agentcore\agentcore.json
Copy-Item agentcore\aws-targets.example.json agentcore\aws-targets.json
```

Populate the local copies as resources are created. These files are intentionally ignored by Git.

The rubric defaults are Claude Haiku 4.5 for orchestration and Claude Sonnet
4.5 for workers. If a classroom account blocks Marketplace-backed models, an
evidence run may temporarily set `ORCHESTRATOR_MODEL_ID` and `WORKER_MODEL_ID`
to an account-accessible Bedrock model such as `amazon.nova-lite-v1:0`. Leave
both variables unset for the submitted default configuration.

## 3. Provision the data plane

Review the templates and parameters in `infrastructure/`. Deploy the S3 data bucket, S3 Vector indexes, DynamoDB tables, IAM role, log group, and Bedrock Knowledge Base prerequisites using the supplied template and helpers.

Before moving on, confirm that every CloudFormation stack reports `CREATE_COMPLETE` or `UPDATE_COMPLETE`. Capture redacted evidence for the private course submission.

## 4. Ingest and synchronize data

Upload the provided e-commerce datasets to the provisioned S3 locations. Create or update the Bedrock knowledge bases and data sources, then start ingestion jobs. Wait for every ingestion job to report `COMPLETE` before testing retrieval.

Write only the resulting knowledge-base identifiers to the local `.env` and `agentcore/aws-targets.json` files.

## 5. Deploy AgentCore

From `agentcore/cdk`, install dependencies and synthesize the CDK application:

```powershell
npm ci
npm run build
npx cdk synth
```

Then run `python src\agent_orchestrator.py deploy` to configure the guardrail, runtime, AgentCore Memory, observability, and optional gateway. Verify the runtime status before invocation.

## 6. Validate

Run source-level checks first, followed by the AWS integration tasks:

```powershell
python -m unittest tests.test_public_repository -v
python tests\test_agent.py task2
python tests\test_agent.py all
```

If a model invocation reports an AWS Marketplace or model-access error, treat it as an account entitlement issue. Do not claim a successful end-to-end response until an invocation actually succeeds.

## 7. Private submission evidence

Capture screenshots only after the relevant status is visible. The course submission may show the Udacity account number, role/resource ARNs, resource IDs, and request/trace IDs when they help an evaluator verify the deployment. Always remove access keys, secret keys, session tokens, passwords, federation URLs, and unrelated personal browser data.

## Cleanup

Preview cleanup first, then provide the exact configured project name for the destructive run:

```powershell
python infrastructure\cleanup.py
python infrastructure\cleanup.py --yes --confirm-project udacity-agentcore --confirm-account <your-aws-account-id>
```

The destructive run requires both the exact project name and the active AWS account ID. Gateway cleanup is limited to the configured project stack's exact gateway name. Its IAM role is deleted only when the project ownership tags, trust policy, and least-privilege inline policy match and no managed policies are attached; unexpected roles are preserved for manual review. Other foundation resources are removed through the named CloudFormation stack rather than a broad name-prefix sweep.

Knowledge-base service roles created manually in the AWS Console are preserved because they may be shared. Review and remove an unused role separately only after confirming its trust policy, attached policies, and resource references.

1. Delete the AgentCore runtime and related endpoints.
2. Empty versioned S3 buckets before deleting their stacks.
3. Delete Bedrock knowledge bases, their data sources, and AgentCore Memory.
4. Delete the S3 Vector indexes and vector bucket when they are no longer needed.
5. Delete DynamoDB tables unless retention is intentional.
6. Delete CloudFormation/CDK stacks and confirm completion.
7. Review CloudWatch log groups, IAM roles, and any retained KMS keys.
8. Recheck the account's billing and cost-management pages.

Never publish authentication credentials. The course repository may include a populated `.env` only when it contains non-secret resource identifiers and has been checked for credential fields and secret patterns.
