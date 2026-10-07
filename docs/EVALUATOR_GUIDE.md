# Evaluator Guide

This guide provides a short, repeatable review path for the Multi-Agent E-commerce RAG assignment.

## Recommended review order

1. Read the root `README.md` for the scope, architecture, setup, and disclosed limitation.
2. Review `docs/RUBRIC_MATRIX.md` for the criterion-to-evidence mapping.
3. Inspect `src/` for the five-agent implementation, retrieval tools, workflow state, runtime entrypoint, and observability.
4. Inspect `infrastructure/` and `agentcore/cdk/` for the AWS resource definitions.
5. Run the credential-free checks below.
6. Run the AWS-backed integration suite only in a deployed and authorized account.

## Credential-free validation

From the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUTF8 = "1"
python -m unittest tests.test_public_repository -v
python tests\test_agent.py task2
```

Task 2 exercises source-level agent and tool behavior without making AWS API calls. It accounts for 40 rubric points.

## AWS-backed validation

After completing `docs/DEPLOYMENT.md` and populating the ignored local configuration:

```powershell
python tests\test_agent.py all
```

The assignment validation result recorded on October 7, 2026 was:

| Task | Area | Result |
|---|---|---:|
| 2 | Agent and tool implementation | 40/40 |
| 3 | AgentCore deployment and guardrails | 20/20 |
| 4 | AgentCore Memory | 15/15 |
| 5 | Bedrock Knowledge Bases and retrieval | 25/25 |
| 6 | CloudWatch and X-Ray observability | 20/20 |
| **Total** | | **120/120** |

## Evidence scope

The public repository intentionally excludes account-specific console captures and identifiers. Screenshots supplied to a course evaluator should be reviewed in the private submission package, where they can be handled according to course policy. Public code, sanitized diagrams, source-level tests, and rubric mappings are retained here.

The 120/120 result means the automated rubric criteria passed against the assignment environment. It is not presented as proof of an unrestricted production deployment. The final requested Claude Haiku 4.5 invocation was blocked in the Udacity account by an AWS Marketplace entitlement requirement; the limitation is disclosed in the README.

## Review checklist

- Confirm the inventory, refund, policy, and communication agents have distinct prompts and tools.
- Confirm retrieval results retain source metadata for grounded responses.
- Confirm workflow state is recorded in DynamoDB and session summaries use AgentCore Memory.
- Confirm orchestration can combine independent specialist calls.
- Confirm the AgentCore HTTP entrypoint accepts a structured request.
- Confirm secrets and account-specific files are absent.
- Confirm cleanup instructions identify the chargeable AWS resources.
