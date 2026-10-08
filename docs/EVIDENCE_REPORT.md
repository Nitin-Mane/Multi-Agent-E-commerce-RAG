# Live Experiment and Screenshot Evidence Report

## Reviewer summary

This report is the single evidence index for the Udacity **Multi-Agent E-commerce RAG** submission. It links original AWS console captures, an original terminal capture, and raw command output without recreating terminal or console screenshots. The 120/120 image below was captured directly from a successful `python tests/test_agent.py all` run.

## Environment verified

| Field | Verified value |
|---|---|
| Evidence date | October 8, 2026 |
| AWS account | `028612373481` (Udacity sandbox) |
| Region | `us-east-1` (N. Virginia) |
| Project | `udacity-agentcore` |
| Runtime | `udacity_agentcore_runtime-u71naiDhDx` |
| Guardrail | `up6axh4lt0of`, version `1` |
| Returns KB | `NYXVNW9GJN` |
| Shipping KB | `BTHTUIKUYI` |
| Warranty KB | `JHJBT4FYVM` |
| Official rubric result | `120/120` |

These account and resource identifiers are intentionally visible for course evaluation. They are not authentication secrets. The repository does **not** contain an AWS access key, secret access key, session token, password, federation URL, or browser sign-in token.

## Fresh end-to-end experiment

The experiment was rerun from the repository root against the Udacity sandbox with the exact rubric entrypoint:

```powershell
$env:PYTHONUTF8 = "1"
$env:ORCHESTRATOR_MODEL_ID = "amazon.nova-lite-v1:0"
python src/agent_orchestrator.py test
```

`PYTHONUTF8=1` prevents the Windows console from rejecting the test runner's Unicode separators. The temporary orchestrator override is required because the Udacity sandbox blocks the Marketplace entitlement used by the submitted Claude Haiku 4.5 default. `config.py` retains the rubric-required Haiku 4.5 default; all worker agents used the submitted Claude Sonnet 4.5 default during this run.

### Observed execution

| Scenario | Observed route | Result |
|---|---|---|
| Return request for `ORD-27176` | Orchestrator -> Inventory -> Policy -> three parallel KB retrievers -> Refund -> Communication | Completed |
| Premium return-policy question | Orchestrator -> Policy -> three parallel KB retrievers -> Communication | Completed |
| Five items at $29.99 with 10% discount | Orchestrator arithmetic -> Communication | Completed; `$134.95` |

The fresh runner reported successful publication of these X-Ray trace IDs:

- `1-6ac7ae3c-fa6b9bf5599f38d19aa67461`
- `1-6ac7ae9d-7e4d7cf4cd1ace20c58080b7`
- `1-6ac7aed7-099404bf4cca8ff9455cc9c8`

After the run, CloudWatch X-Ray was refreshed with the **5 minute** range in `us-east-1`. The live map showed `NovaMart-Orchestrator` connected to `InventoryAgent`, `PolicyAgent`, `RefundAgent`, `CommunicationAgent`, `KnowledgeBase-returns`, `KnowledgeBase-shipping`, and `KnowledgeBase-warranty`.

## Required X-Ray Service Map evidence

![Original AWS X-Ray Service Map showing NovaMart-Orchestrator, worker agents, and three Knowledge Base nodes](../evidence/screenshots/aws-xray-service-map.png)

### What the reviewer should verify

1. The AWS console is on the X-Ray/CloudWatch Trace Map in `us-east-1`.
2. `NovaMart-Orchestrator` is the central service node.
3. Worker nodes include `InventoryAgent`, `PolicyAgent`, `RefundAgent`, and `CommunicationAgent`.
4. Policy retrieval includes the returns, shipping, and warranty Knowledge Base nodes.
5. Directed edges form the required orchestrator -> worker -> Knowledge Base call chain.

This is an original AWS Console capture, not a Mermaid diagram or a reconstructed graphic. The live map was regenerated and visually rechecked after the fresh experiment above.

## Official test evidence

![Original PowerShell terminal capture showing the official command, exit code 0, and 120 out of 120 points](../evidence/screenshots/official-tests-120-of-120.png)

The complete output from the fresh command is preserved as [`official-all-tasks-2026-10-08-original.txt`](../evidence/transcripts/official-all-tasks-2026-10-08-original.txt). The earlier sanitized record remains available as [`official-all-tasks-sanitized.txt`](../evidence/transcripts/official-all-tasks-sanitized.txt). Both end with `120/120 pts (100%)`. No recreated terminal rendering is included.

| Task | Rubric area | Recorded score |
|---|---|---:|
| Task 2 | Multi-agent graph, tools, models, and routing | 40/40 |
| Task 3 | Guardrail and AgentCore Runtime | 20/20 |
| Task 4 | AgentCore Memory | 15/15 |
| Task 5 | Knowledge Bases and parallel retrieval | 25/25 |
| Task 6 | CloudWatch and X-Ray observability | 20/20 |
| **Total** | **Official rubric verification** | **120/120** |

### Runtime and Knowledge Base console evidence

- [Original AgentCore Runtime console capture](../evidence/screenshots/aws-agentcore-runtime.jpg)
- [Original three-Knowledge-Base console capture](../evidence/screenshots/aws-knowledge-bases.jpg)
- [Sanitized Task 3 runtime and guardrail output](../evidence/transcripts/task3-runtime-guardrail-sanitized.txt)
- [Sanitized Task 5 retrieval output with non-empty returns, shipping, and warranty passages](../evidence/transcripts/task5-kb-retrieval-sanitized.txt)
- [Sanitized Task 6 output recorded after traces arrived](../evidence/transcripts/task6-observability-after-traces-sanitized.txt)
- [Sanitized live trace-generation output](../evidence/transcripts/trace-generation-mixed-model-sanitized.txt)
- [Fresh original trace-generation output](../evidence/transcripts/trace-generation-2026-10-08-original.txt)

## Architecture cross-reference

The [Architecture document](ARCHITECTURE.md#request-flow) owns the request-flow figure, Mermaid diagrams, role/tool matrix, and Shared `WorkflowState` explanation. This report is the only documentation page that embeds or directly indexes observed execution evidence.

## Evidence-to-source traceability

| Claim | Primary artifact | Automated or live check |
|---|---|---|
| All TODO requirements implemented | `src/agent_orchestrator.py` | `python tests/test_agent.py task2` |
| Five-agent graph and tool counts | Agent builders and routing tools | Official Task 2 checks |
| Deterministic routing contract | Orchestrator prompt and `tests/test_routing_contract.py` | Routing unit tests |
| Parallel three-KB retrieval | `build_policy_agent()` and `ThreadPoolExecutor` | Official Tasks 2 and 5 plus live output |
| Guardrail and runtime | deployment helpers, `.env`, runtime screenshot, and Task 3 transcript | Official Task 3 checks |
| Seven-day session summaries | `configure_memory()` | Official Task 4 checks |
| Three synchronized KBs | `infrastructure/create_knowledge_bases.py`, `.env`, KB screenshot, and Task 5 transcript | Official Task 5 checks and live retrieval |
| Distributed tracing | `src/agent_observability.py` | Official Task 6, fresh trace IDs, X-Ray screenshot |
| No published AWS credentials | repository safety test | `python -m unittest tests.test_public_repository -v` |

## Security boundary

Included for evaluation:

- Udacity AWS account number
- Guardrail, Knowledge Base, runtime, request, and trace identifiers
- original AgentCore Runtime, Knowledge Base, and AWS X-Ray console screenshots
- original terminal screenshot from `python tests/test_agent.py all`
- sanitized raw official-test and live-experiment transcripts
- populated non-secret `.env`

Never included:

- AWS access keys
- AWS secret access keys
- AWS session tokens
- passwords, OTPs, or federation/sign-in URLs
- personal-account credentials
