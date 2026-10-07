# Architecture Notes

## System design

The solution separates coordination from domain work. The orchestrator interprets a customer request, chooses one or more specialists, and produces a single response. Each specialist owns a narrow prompt and a minimal tool surface, making behavior easier to test and reason about.

```text
Client
  |
  v
AgentCore Runtime -> Orchestrator
                       |-- Inventory Agent ----> DynamoDB orders/customers
                       |-- Refund Agent -------> DynamoDB order updates
                       |-- Policy Agent --------> Returns / Shipping / Warranty KBs
                       `-- Communication Agent -> Customer-ready response
                               |                         |
                               +-------------------------+
                                           |
                DynamoDB Workflow State + AgentCore Memory
```

## Request flow

1. AgentCore passes a structured request to `run_serve()` in `src/agent_orchestrator.py`.
2. The HTTP entrypoint validates the request and initializes the orchestrator.
3. The orchestrator classifies the intent and records workflow progress.
4. Relevant specialists retrieve domain context and produce focused results.
5. Independent work can execute concurrently when a request spans domains.
6. The orchestrator combines the specialist outputs into the final answer.
7. The workflow record is finalized for traceability and recovery.

## State consistency

The orchestrator creates a DynamoDB workflow record for each session, and routing tools append structured worker output as the request advances. AgentCore Memory complements this operational state with a `SESSION_SUMMARY` strategy and seven-day event expiry for conversational continuity.

## Retrieval design

The retrieval wrapper isolates Bedrock Knowledge Bases API details from agent prompts. The PolicyAgent fans out to separate returns, shipping, and warranty retrievers with `ThreadPoolExecutor`, then combines their grounded passages. This boundary keeps agent code focused on decision-making while allowing retrieval behavior to be tested separately.

## Safety and operations

- Input and configuration are validated at service boundaries.
- Guardrail outcomes are handled as controlled responses.
- Credentials are never written to traces. Raw request text can be included only through an explicit debugging opt-in, so use synthetic course data and apply appropriate log retention and access controls.
- By default, telemetry uses process-local keyed pseudonyms for customer/session identifiers, omits request text, and records tool argument names without their values. Sensitive trace metadata requires an explicit local opt-in.
- The optional Gateway requires AWS IAM authorization and uses a tagged, dedicated role scoped to the resolved Lambda targets. Existing resources are reused only when their identity and permission boundary match.
- Resource names and identifiers are loaded from the environment or ignored local files.
- Cleanup is part of the deployment lifecycle because model calls, storage, S3 Vectors, and logs can incur charges.
