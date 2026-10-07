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
- Account-specific screenshots belong in the private course submission, not in this public repository.

## Limit disclosure

The Udacity sandbox passed all automated rubric resource checks. The final live call to Claude Haiku 4.5 was not completed because the sandbox lacked the required AWS Marketplace entitlement. This distinction prevents a resource-validation result from being misrepresented as a successful live-model response.
