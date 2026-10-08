# Architecture Notes

This document explains the implementation decisions behind NovaMart's multi-agent customer-support workflow. For the deployment-level AWS view, see [System Architecture](SYSTEM_ARCHITECTURE.md).

## Architecture overview

```mermaid
flowchart TB
    Client([Customer / API client]) -->|IAM-authorized request| Runtime[Amazon Bedrock<br/>AgentCore Runtime]
    Runtime --> Guardrail[Amazon Bedrock Guardrail]
    Guardrail --> Orchestrator[OrchestratorAgent<br/>intent classification and routing]

    Orchestrator --> Inventory[InventoryAgent<br/>order and customer facts]
    Orchestrator --> Policy[PolicyAgent<br/>grounded policy synthesis]
    Orchestrator --> Refund[RefundAgent<br/>eligibility and refund action]
    Orchestrator --> Communication[CommunicationAgent<br/>customer-ready response]

    Inventory --> Commerce[(Orders and Customers<br/>DynamoDB tables)]
    Refund --> Commerce
    Policy --> Returns[Returns retriever]
    Policy --> Shipping[Shipping retriever]
    Policy --> Warranty[Warranty retriever]
    Returns --> KB[(Bedrock Knowledge Bases<br/>with S3 Vectors)]
    Shipping --> KB
    Warranty --> KB

    Orchestrator <--> State[(DynamoDB<br/>WorkflowStateTable)]
    Inventory --> State
    Policy --> State
    Refund --> State
    Communication --> State
    Runtime <--> Memory[AgentCore Memory<br/>7-day session summaries]
    Runtime --> Observe[CloudWatch Logs<br/>and AWS X-Ray]

    classDef entry fill:#232F3E,color:#FFFFFF,stroke:#8FA7C1,stroke-width:2px;
    classDef control fill:#146EB4,color:#FFFFFF,stroke:#0B4F86,stroke-width:2px;
    classDef worker fill:#6B3FD4,color:#FFFFFF,stroke:#4A2A96,stroke-width:2px;
    classDef data fill:#E8F1FB,color:#172B4D,stroke:#146EB4,stroke-width:2px;
    classDef ops fill:#E9F7EF,color:#173F2A,stroke:#1F883D,stroke-width:2px;
    class Client entry;
    class Runtime,Guardrail,Orchestrator control;
    class Inventory,Policy,Refund,Communication,Returns,Shipping,Warranty worker;
    class Commerce,KB,State,Memory data;
    class Observe ops;
```

The solution separates coordination from domain work. The orchestrator owns routing and sequencing, while each worker owns a narrow prompt and minimal tool surface. This makes routing independently testable and keeps policy retrieval, transactional work, and customer communication from becoming one oversized prompt.

## Agent and retrieval design

```mermaid
flowchart LR
    O[OrchestratorAgent] -->|facts| I[InventoryAgent]
    O -->|policy| P[PolicyAgent]
    O -->|decision| R[RefundAgent]
    O -->|always last| C[CommunicationAgent]

    P --> FanOut{ThreadPoolExecutor<br/>max_workers = 3}
    FanOut --> RR[ReturnsPolicyRetriever]
    FanOut --> SR[ShippingPolicyRetriever]
    FanOut --> WR[WarrantyPolicyRetriever]
    RR --> RKB[(Returns KB)]
    SR --> SKB[(Shipping KB)]
    WR --> WKB[(Warranty KB)]
    RKB --> Join[Grounded policy synthesis]
    SKB --> Join
    WKB --> Join
    Join --> P

    classDef orchestrator fill:#146EB4,color:#FFFFFF,stroke:#0B4F86,stroke-width:2px;
    classDef agent fill:#6B3FD4,color:#FFFFFF,stroke:#4A2A96,stroke-width:2px;
    classDef retrieve fill:#007A78,color:#FFFFFF,stroke:#005C5A,stroke-width:2px;
    classDef store fill:#FF9900,color:#111827,stroke:#B36B00,stroke-width:2px;
    class O orchestrator;
    class I,P,R,C agent;
    class FanOut,RR,SR,WR,Join retrieve;
    class RKB,SKB,WKB store;
```

The PolicyAgent fans out to three independent retrievers and joins their results before synthesis. The retrieval wrapper isolates Bedrock Knowledge Bases API details from agent prompts, keeping the agent focused on reasoning over grounded passages.

## Request flow

```mermaid
sequenceDiagram
    autonumber
    actor Customer
    participant Runtime as AgentCore Runtime
    participant O as OrchestratorAgent
    participant W as WorkflowStateTable
    participant Specialist as Required specialist(s)
    participant C as CommunicationAgent

    Customer->>Runtime: request + session_id + customer_id
    Runtime->>O: validated payload
    O->>W: initialize_session()
    W-->>O: version 0
    O->>Specialist: route according to intent contract
    Specialist->>W: conditional result update
    W-->>Specialist: version incremented
    Specialist-->>O: focused structured result
    O->>C: route_to_communication_agent()
    C->>W: get_full_workflow_context()
    W-->>C: accumulated specialist results
    C-->>O: customer-ready response
    O-->>Runtime: final response
    Runtime-->>Customer: guarded response
```

The routing contract is explicit:

| Request type | Route before final communication |
|---|---|
| Account details or customer tier | Inventory only; never Policy |
| Order status or history | Inventory, then Refund for evaluation only |
| Policy-only question | Policy |
| Explicit return or refund | Inventory, then Policy, then Refund |
| Mixed order and policy | Inventory, then Policy |
| Arithmetic | Orchestrator calculation; no Inventory, Policy, or Refund |

CommunicationAgent is always the final worker. An order-status route through RefundAgent evaluates status or eligibility; it never authorizes a refund unless the customer explicitly requests one.

![Request-flow scenarios for order, policy, and direct-answer paths](../diagrams/request-flow-scenarios.png)

*Figure 1 — Representative execution paths. Every path uses shared workflow state and ends with CommunicationAgent.*

## Shared state and consistency

```mermaid
flowchart LR
    Create[initialize_session<br/>version 0] --> Read[Worker reads current state]
    Read --> Execute[Worker produces result]
    Execute --> Write{Conditional update<br/>version = expected_version}
    Write -->|success| Commit[Store worker column<br/>increment version]
    Write -->|conflict| Reload[Reload latest record]
    Reload --> Retry[Retry, maximum 3 attempts]
    Retry --> Write
    Commit --> Next{More workers?}
    Next -->|yes| Read
    Next -->|no| Complete[Final response stored]

    classDef action fill:#146EB4,color:#FFFFFF,stroke:#0B4F86,stroke-width:2px;
    classDef decision fill:#FFB000,color:#111827,stroke:#B36B00,stroke-width:2px;
    classDef success fill:#1F883D,color:#FFFFFF,stroke:#116329,stroke-width:2px;
    classDef retry fill:#C93756,color:#FFFFFF,stroke:#8E243B,stroke-width:2px;
    class Create,Read,Execute action;
    class Write,Next decision;
    class Commit,Complete success;
    class Reload,Retry retry;
```

`WorkflowStateTable` uses `session_id` as its partition key. The record stores `customer_id`, `created_at`, a 24-hour `ttl`, a monotonic `version`, and one result column per worker. `_update_workflow_state()` uses `expected_version` in a DynamoDB condition and retries after conflicts, preventing stale workers from silently overwriting newer results.

AgentCore Memory is complementary rather than duplicated storage: DynamoDB holds one request's structured operational state, while the `SESSION_SUMMARY` strategy retains conversational summaries for seven days.

## Verification evidence

![Sanitized official rubric verification showing 120 out of 120](../diagrams/official-tests-120-of-120-redacted.png)

*Figure 2 — Sanitized rendering of the recorded official rubric result. The AWS account number is intentionally redacted; the original evidence remains in the private submission package.*

The recorded rubric run reports **120/120** across the multi-agent graph, AgentCore runtime and guardrail, AgentCore Memory, knowledge bases, and observability. This score verifies the rubric checks captured in the private evidence; it does not claim a successful live-model response where the Udacity sandbox lacked the required model entitlement.

## Safety and operations

- Service boundaries validate input and configuration before invoking agents.
- Bedrock Guardrail outcomes become controlled responses rather than unhandled failures.
- Telemetry uses process-local keyed pseudonyms by default, omits raw request text, and records tool argument names without their values.
- Resource identifiers come from environment variables or ignored local configuration files.
- The optional AgentCore Gateway uses IAM authorization and a dedicated role restricted to configured Lambda targets.
- Cleanup is part of the lifecycle because model calls, storage, S3 Vectors, memory, and logs can incur charges.
