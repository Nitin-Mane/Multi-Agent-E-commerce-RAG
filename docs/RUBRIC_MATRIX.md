# Rubric Traceability Matrix

The matrix maps each assignment area to inspectable code and validation. Point totals reflect the course's automated rubric run completed on October 8, 2026.

| Task | Criterion | Implementation evidence | Validation evidence | Points |
|---|---|---|---|---:|
| 2 | Inventory agent and its three tools | `build_inventory_agent()` in `src/agent_orchestrator.py` | Credential-free Task 2 | 10 |
| 2 | Policy agent and parallel retrieval tool | `build_policy_agent()` and `ThreadPoolExecutor` fan-out | Credential-free Task 2 | 10 |
| 2 | Orchestrator and five routing tools | `build_orchestrator_agent()` | Credential-free Task 2 | 10 |
| 2 | Routing and worker model assignments | `config.ORCHESTRATOR_MODEL_ID`, `config.WORKER_MODEL_ID` | Credential-free Task 2 | 10 |
| 3 | Bedrock guardrail and required policies | Guardrail deployment in `src/agent_orchestrator.py` | AWS-backed Task 3 | 13 |
| 3 | READY AgentCore HTTP runtime | `src/agentcore_cli.py`, sanitized AgentCore template | AWS-backed Task 3 | 7 |
| 4 | ACTIVE AgentCore Memory | `configure_memory()` with summarization and seven-day expiry | AWS-backed Task 4 | 15 |
| 5 | Returns, shipping, and warranty knowledge bases | `infrastructure/create_knowledge_bases.py` | AWS-backed Task 5 | 15 |
| 5 | Live retrieval and combined policy search | `src/bedrock_kb_retrieval.py`, `search_all_policies()` | AWS-backed Task 5 | 10 |
| 6 | CloudWatch logging at INFO level | `src/agent_observability.py`, runtime environment | AWS-backed Task 6 | 10 |
| 6 | X-Ray tracing and Transaction Search | `src/agent_observability.py`, deployment configuration | AWS-backed Task 6 | 10 |
| | **Total** | | | **120** |

## Interpretation

- `tests/test_agent.py task2` is credential-free and repeatable from a local clone.
- Tasks 3-6 are integration checks and need provisioned AWS resources plus local ignored identifiers.
- Public-repository checks verify that required evaluator documentation exists and common sensitive-data patterns are absent.
- The course repository includes the AWS screenshots and test transcripts needed to reproduce the evaluation record.
- A graphical score summary is not accepted as terminal evidence. The required score image must be captured directly from a successful `python tests/test_agent.py all` run.

## Recommended evaluator sequence

1. Read the root [README](../README.md) for scope, setup, and the disclosed model-entitlement limitation.
2. Review [Architecture](ARCHITECTURE.md) for the AWS topology, Agent Graph, Request Flow, Shared `WorkflowState`, and role/tool boundaries.
3. Inspect `src/agent_orchestrator.py` for completed orchestration, worker, state, retrieval, deployment, and tracing logic.
4. Review the **120/120** transcript and AWS console captures in the [Evidence Report](EVIDENCE_REPORT.md).
5. Inspect the populated [`.env`](../.env) and confirm that the documented resource IDs are present.
6. Run the local validation commands below.

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUTF8 = "1"
python -m unittest tests.test_public_repository tests.test_documentation_structure -v
python tests\test_agent.py task2
```

Run the AWS-backed suite only with authorized temporary credentials and deployed resources:

```powershell
python tests\test_agent.py all
```

## Evaluator checklist

- Confirm the inventory, refund, policy, and communication agents have distinct prompts and tool boundaries.
- Confirm policy retrieval fans out to returns, shipping, and warranty knowledge bases and retains source metadata.
- Confirm workflow state is stored in DynamoDB and session summaries use AgentCore Memory.
- Confirm account/tier requests use InventoryAgent and never PolicyAgent.
- Confirm order status routes InventoryAgent -> RefundAgent -> CommunicationAgent without initiating an unrequested refund.
- Confirm CommunicationAgent is the final worker for every route.
- Confirm the AgentCore HTTP entrypoint accepts a structured request.
- Confirm `.env` contains the resource IDs used by the evaluated deployment.
- Confirm the 120/120 image is an original terminal capture from the official command, not a recreated rendering.
- Confirm the X-Ray image shows `NovaMart-Orchestrator` connected to workers and Knowledge Base nodes.
- Confirm cleanup guidance identifies the chargeable AWS resources.

## Limit disclosure

The Udacity sandbox passed all automated rubric resource checks. It did not provide the Marketplace entitlement for the rubric-default Claude Haiku 4.5 orchestrator, so the documented live evidence run used Nova Lite for orchestration while retaining Claude Sonnet 4.5 for the workers. The submitted default in `config.py` remains unchanged.
