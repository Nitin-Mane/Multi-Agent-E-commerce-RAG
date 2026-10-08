# Rubric Traceability Matrix

The matrix maps each assignment area to inspectable code and validation. Point totals reflect the course's automated rubric run completed on October 7, 2026.

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
- The course repository includes the original account-specific X-Ray screenshot, the rendered 120/120 summary, and its retained result record; authentication credentials remain excluded.

## Recommended evaluator sequence

1. Read the root [README](../README.md) for scope, setup, and the disclosed model-entitlement limitation.
2. Review [Architecture](ARCHITECTURE.md) for the AWS topology, Agent Graph, Request Flow, Shared `WorkflowState`, and role/tool boundaries.
3. Inspect `src/agent_orchestrator.py` for completed orchestration, worker, state, retrieval, deployment, and tracing logic.
4. Review the recorded **120/120** result summary and original AWS X-Ray Service Map in the [Evidence Report](EVIDENCE_REPORT.md).
5. Inspect the populated [`.env`](../.env) and confirm that resource IDs are present while credential variables are absent.
6. Run the credential-free validation commands below.

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
- Confirm `.env` contains required non-secret resource IDs and no AWS credential values.
- Confirm the X-Ray image shows `NovaMart-Orchestrator` connected to workers and Knowledge Base nodes.
- Confirm cleanup guidance identifies the chargeable AWS resources.

## Limit disclosure

The Udacity sandbox passed all automated rubric resource checks. The final live call to Claude Haiku 4.5 was not completed because the sandbox lacked the required AWS Marketplace entitlement. This distinction prevents a resource-validation result from being misrepresented as a successful live-model response.
