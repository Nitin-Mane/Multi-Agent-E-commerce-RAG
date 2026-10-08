# Screenshot Evidence Report

## Purpose and evidence boundary

This report helps an evaluator connect the project screenshots to the implementation and rubric. It distinguishes three different kinds of evidence:

1. **Public presentation evidence** explains the architecture and request flow without exposing deployed identifiers.
2. **Sanitized verification evidence** reports recorded test outcomes after account details have been removed.
3. **Private deployment evidence** contains account-specific resource identifiers and remains in the course submission package rather than the public repository.

Screenshots complement the source code and raw test output; they do not replace them. The authoritative implementation is in `src/`, `config.py`, `infrastructure/`, and `agentcore/cdk/`. The authoritative criterion mapping is in [Rubric Matrix](RUBRIC_MATRIX.md).

## Public architecture overview

![NovaMart multi-agent architecture overview](../diagrams/architecture-overview.png)

### What this screenshot shows

- A supervisor-and-workers architecture with OrchestratorAgent coordinating InventoryAgent, PolicyAgent, RefundAgent, and CommunicationAgent.
- Shared workflow state stored in DynamoDB.
- Parallel retrieval beneath PolicyAgent.
- The primary platform components: Strands Agents, Amazon Bedrock AgentCore, Bedrock foundation models, DynamoDB, Bedrock Knowledge Bases, S3 Vectors, and `ThreadPoolExecutor`.

### How to interpret it

This is a presentation-level overview rather than a deployment console capture. The diagram is intentionally compact; [System Architecture](SYSTEM_ARCHITECTURE.md) contains the implementation-level topology and color-coded Mermaid diagrams. `config.py` is authoritative for the submitted Claude Haiku 4.5 orchestrator and Claude Sonnet 4.5 worker defaults.

### Rubric relationship

| Rubric area | Supporting implementation |
|---|---|
| Task 2 — multi-agent graph | `src/agent_orchestrator.py` agent builders and routing tools |
| Task 4 — shared context | DynamoDB `WorkflowStateTable` and AgentCore Memory configuration |
| Task 5 — multi-agent RAG | PolicyAgent with three parallel knowledge-base retrievers |

## Public request-flow scenarios

![Order, policy, and direct-answer request flows](../diagrams/request-flow-scenarios.png)

### What this screenshot shows

- **Order or return path:** session initialization, inventory lookup, refund/status evaluation, and final communication.
- **Policy path:** PolicyAgent coordinates three retrievers in parallel before CommunicationAgent writes the response.
- **Calculation path:** the orchestrator handles arithmetic without unnecessary domain workers but still calls CommunicationAgent last.
- DynamoDB workflow state persists the session and each completed worker result across every path.

### Routing details reviewers should verify

| Request type | Expected workers before CommunicationAgent |
|---|---|
| Account or customer tier | Inventory only; never Policy |
| Order status or history | Inventory, then Refund for evaluation only |
| Policy-only question | Policy |
| Explicit return or refund | Inventory, then Policy, then Refund |
| Mixed order and policy | Inventory, then Policy |
| Arithmetic | No Inventory, Policy, or Refund worker |

RefundAgent appearing in the order-status route does not mean a refund is automatically created. The routing prompt explicitly prohibits initiating a refund unless the customer requests one. These invariants are covered by `tests/test_routing_contract.py`.

## Sanitized official test result

![Sanitized official rubric verification showing 120 out of 120](../diagrams/official-tests-120-of-120-redacted.png)

### Recorded result

| Task | Evidence category | Recorded score |
|---|---|---:|
| Task 2 | Multi-agent graph and tools | 40/40 |
| Task 3 | Guardrail and AgentCore Runtime | 20/20 |
| Task 4 | AgentCore Memory | 15/15 |
| Task 5 | Knowledge bases and retrieval | 25/25 |
| Task 6 | CloudWatch and X-Ray | 20/20 |
| **Total** | **Official rubric verification** | **120/120** |

The public image is a privacy-redacted rendering of the recorded result. The AWS account number was removed before publication. The unmodified evidence record remains in the private submission package.

### Important limitation

The recorded rubric and resource checks passed, but the final live Claude Haiku invocation in the Udacity sandbox was blocked by an AWS Marketplace model-entitlement restriction. The repository therefore does not claim a successful end-to-end model response from that sandbox. This limitation is separate from the verified provisioning, code, retrieval, memory, and observability outcomes.

## Complete screenshot inventory

The following table documents all seven screenshots supplied with the private course submission. Only rows marked **Public** are embedded in this repository.

| File | Evidence represented | Rubric mapping | Publication status | Reviewer note |
|---|---|---|---|---|
| `01-aws-deployment-evidence.png` | Foundation stack, runtime stack, AgentCore Runtime, Memory, Guardrail, and network status | Tasks 3 and 4 | **Private** | Contains the Udacity account number and deployed resource identifiers. Use the private submission copy to verify account-specific deployment state. |
| `02-knowledge-bases-evidence.png` | Returns, shipping, and warranty knowledge bases; synchronization; parallel retrieval score | Task 5 | **Private** | Contains deployed knowledge-base identifiers. The public architecture report documents the same component relationships without those identifiers. |
| `03-observability-evidence.png` | Runtime readiness, CloudWatch logging, log group, X-Ray indexing, request receipt, and score | Task 6 | **Private** | Contains runtime/log resource details. It also records that the request reached AgentCore before the model-entitlement failure. |
| `04-official-tests-120-of-120.png` | Consolidated official test scores for Tasks 2–6 | Tasks 2–6 | **Public after redaction** | Published as `official-tests-120-of-120-redacted.png`; the account number is removed. |
| `05-architecture-overview.png` | Supervisor/worker architecture, parallel RAG, and shared workflow state | Tasks 2, 4, and 5 | **Public** | Used as the README cover and embedded above. Model defaults in `config.py` remain authoritative. |
| `06-agents-and-tools-reference.png` | Agent responsibilities, tool inventory, and workflow-state schema | Tasks 2 and 4 | **Private reference** | The visual contains older model labels. The current submitted defaults and tool matrix are documented in [System Architecture](SYSTEM_ARCHITECTURE.md). |
| `07-request-flow-scenarios.png` | Order/refund, policy, and direct-answer routes | Task 2 | **Public** | Embedded above; detailed routing assertions are implemented in `tests/test_routing_contract.py`. |

## Evidence-to-source traceability

| Evidence claim | Primary source | Automated check |
|---|---|---|
| Five-agent orchestration and tool counts | `src/agent_orchestrator.py` | `tests/test_agent.py task2` |
| Six-rule routing contract | Orchestrator system prompt | `tests/test_routing_contract.py` |
| Claude model defaults with lab-safe overrides | `config.py` | `tests/test_model_configuration.py` |
| Optimistic workflow-state updates | `_update_workflow_state()` | Task 2 structure checks and source review |
| Parallel policy retrieval | `build_policy_agent()` and `ThreadPoolExecutor` | Task 2 parallel-execution check |
| Guardrail and runtime deployment | `create_guardrail()` and runtime deployment helpers | Official Task 3 checks |
| Seven-day session summaries | `configure_memory()` | Official Task 4 checks |
| Three synchronized knowledge bases | `infrastructure/create_knowledge_bases.py` | Official Task 5 checks |
| CloudWatch and X-Ray configuration | `src/agent_observability.py` | Official Task 6 checks |
| Public-repository privacy | `.gitignore`, examples, and sanitized assets | `tests/test_public_repository.py` and `tests/test_security_defaults.py` |

## Recommended evaluator sequence

1. Review the inline architecture diagram in the [README](../README.md).
2. Inspect the implementation-level diagrams in [System Architecture](SYSTEM_ARCHITECTURE.md).
3. Compare the expected routes above with the orchestrator prompt and routing tests.
4. Review the [Rubric Matrix](RUBRIC_MATRIX.md) for criterion-level evidence.
5. Use the private submission package for raw outputs and account-specific screenshots.
6. Treat the Marketplace entitlement as a documented sandbox limitation, not as evidence of a successful live-model response.

## Privacy controls applied

- No AWS access key, secret key, or session token is included.
- The public test-result image contains no AWS account number.
- Deployed runtime, memory, guardrail, knowledge-base, and log-group identifiers remain private.
- The repository uses placeholders for local configuration and ignores generated deployment artifacts.
- Public telemetry guidance omits raw request text and tool argument values by default.
