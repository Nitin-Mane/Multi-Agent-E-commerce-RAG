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

The submitted `.env` is already populated with non-secret Udacity resource identifiers. Authenticate with an authorized temporary role, then run:

```powershell
python tests\test_agent.py all
```

The current credential-free validation result is:

| Task | Area | Result |
|---|---|---:|
| 2 | Agent and tool implementation | 40/40 |
| 3 | AgentCore deployment and guardrails | 20/20 |
| 4 | AgentCore Memory | 15/15 |
| 5 | Bedrock Knowledge Bases and retrieval | 25/25 |
| 6 | CloudWatch and X-Ray observability | 20/20 plus original service-map evidence |

## Evidence scope

The repository intentionally includes the Udacity account number, deployed resource identifiers, original 120/120 test screenshot, and original X-Ray map so the GitHub archive contains every required review artifact. These are non-secret identifiers. Access keys, secret keys, session tokens, passwords, and federation URLs are excluded.

AWS-backed claims are intentionally made only when supported by the raw, sanitized output and console captures packaged for the evaluator. Public documentation does not substitute diagrams for live AWS evidence.

## Review checklist

- Confirm the inventory, refund, policy, and communication agents have distinct prompts and tools.
- Confirm retrieval results retain source metadata for grounded responses.
- Confirm workflow state is recorded in DynamoDB and session summaries use AgentCore Memory.
- Confirm orchestration can combine independent specialist calls.
- Confirm account/tier requests use InventoryAgent and never PolicyAgent.
- Confirm order status routes InventoryAgent -> RefundAgent -> CommunicationAgent without initiating an unrequested refund.
- Confirm the AgentCore HTTP entrypoint accepts a structured request.
- Confirm `.env` contains the required resource IDs but no credential variables or secret values.
- Confirm `diagrams/aws-xray-service-map-original.jpg` shows `NovaMart-Orchestrator` connected to worker and Knowledge Base nodes.
- Confirm cleanup instructions identify the chargeable AWS resources.
