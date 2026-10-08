# System Architecture

This document provides four complementary views of the NovaMart solution: AWS deployment topology, agent relationships, request sequencing, and shared workflow state. Mermaid source is stored with the documentation so reviewers can inspect and render every diagram directly in GitHub.

## AWS deployment topology

```mermaid
flowchart TB
    User([Customer / evaluator]) -->|HTTPS request| Entry[AgentCore Runtime endpoint]

    subgraph AWS[AWS account boundary]
        direction TB
        Entry --> Guardrail[Amazon Bedrock Guardrail]
        Guardrail --> Orchestrator[OrchestratorAgent<br/>Claude Haiku 4.5]

        subgraph Agents[Strands multi-agent application]
            direction LR
            Inventory[InventoryAgent]
            Policy[PolicyAgent]
            Refund[RefundAgent]
            Communication[CommunicationAgent]
        end

        Orchestrator --> Inventory
        Orchestrator --> Policy
        Orchestrator --> Refund
        Orchestrator --> Communication

        Inventory --> Business[(Orders and Customers<br/>DynamoDB tables)]
        Refund --> Business
        Policy --> Retrieval[Parallel policy retrieval]
        Retrieval --> KB[(3 Bedrock Knowledge Bases)]
        KB --> Vectors[(S3 Vectors)]
        Vectors --> Documents[(S3 policy documents)]

        Orchestrator <--> Workflow[(DynamoDB<br/>WorkflowStateTable)]
        Inventory --> Workflow
        Policy --> Workflow
        Refund --> Workflow
        Communication --> Workflow

        Entry <--> Memory[AgentCore Memory<br/>SESSION_SUMMARY / 7 days]
        Entry --> Logs[CloudWatch Logs]
        Entry --> Traces[AWS X-Ray]
    end

    Communication -->|final response| Entry
    Entry --> User

    classDef external fill:#232F3E,color:#FFFFFF,stroke:#8FA7C1,stroke-width:2px;
    classDef managed fill:#146EB4,color:#FFFFFF,stroke:#0B4F86,stroke-width:2px;
    classDef agent fill:#6B3FD4,color:#FFFFFF,stroke:#4A2A96,stroke-width:2px;
    classDef data fill:#FF9900,color:#111827,stroke:#B36B00,stroke-width:2px;
    classDef observe fill:#1F883D,color:#FFFFFF,stroke:#116329,stroke-width:2px;
    class User external;
    class Entry,Guardrail,Orchestrator,Retrieval managed;
    class Inventory,Policy,Refund,Communication agent;
    class Business,KB,Vectors,Documents,Workflow,Memory data;
    class Logs,Traces observe;
```

**Legend:** dark slate = external actor; blue = AWS managed/control plane; purple = application agents; orange = persistent or retrieval data; green = observability.

## Agent Graph

```mermaid
flowchart TD
    Customer([Customer request]) --> O[OrchestratorAgent<br/>Claude Haiku 4.5 / temp 0.0]
    O -->|order and customer facts| I[InventoryAgent<br/>Claude Sonnet 4.5 / temp 0.1]
    O -->|policy interpretation| P[PolicyAgent<br/>Claude Sonnet 4.5 / temp 0.2]
    O -->|status, eligibility, or explicit action| R[RefundAgent<br/>Claude Sonnet 4.5 / temp 0.1]
    O -->|mandatory final worker| C[CommunicationAgent<br/>Claude Sonnet 4.5 / temp 0.3]

    P --> FanOut{Parallel fan-out}
    FanOut --> PR1[ReturnsPolicyRetriever<br/>temp 0.0]
    FanOut --> PR2[ShippingPolicyRetriever<br/>temp 0.0]
    FanOut --> PR3[WarrantyPolicyRetriever<br/>temp 0.0]
    PR1 --> KB1[(Returns Knowledge Base)]
    PR2 --> KB2[(Shipping Knowledge Base)]
    PR3 --> KB3[(Warranty Knowledge Base)]

    O <--> WS[(WorkflowStateTable)]
    I --> WS
    P --> WS
    R --> WS
    C --> WS

    classDef user fill:#232F3E,color:#FFFFFF,stroke:#8FA7C1,stroke-width:2px;
    classDef orchestrator fill:#146EB4,color:#FFFFFF,stroke:#0B4F86,stroke-width:3px;
    classDef worker fill:#6B3FD4,color:#FFFFFF,stroke:#4A2A96,stroke-width:2px;
    classDef retrieval fill:#007A78,color:#FFFFFF,stroke:#005C5A,stroke-width:2px;
    classDef store fill:#FF9900,color:#111827,stroke:#B36B00,stroke-width:2px;
    class Customer user;
    class O orchestrator;
    class I,P,R,C worker;
    class FanOut,PR1,PR2,PR3 retrieval;
    class KB1,KB2,KB3,WS store;
```

| Agent | Responsibility | Tools |
|---|---|---|
| OrchestratorAgent | Initialize state, choose specialists, enforce the routing contract, and call Communication last | `initialize_session`, four `route_to_*` tools |
| InventoryAgent | Retrieve order and customer facts without making policy decisions | `check_order_status`, `get_customer_tier`, `list_customer_orders` |
| PolicyAgent | Retrieve three policy domains concurrently and synthesize grounded context | `search_all_policies` |
| RefundAgent | Evaluate return status/eligibility and initiate only an explicitly requested eligible refund | `get_inventory_context`, `initiate_refund` |
| CommunicationAgent | Read accumulated state and compose the final customer-facing response | `get_full_workflow_context` |

## Request Flow

```mermaid
sequenceDiagram
    autonumber
    actor Customer
    participant RT as AgentCore Runtime
    participant O as OrchestratorAgent
    participant W as WorkflowStateTable
    participant I as InventoryAgent
    participant P as PolicyAgent
    participant R as RefundAgent
    participant C as CommunicationAgent

    Customer->>RT: request, session_id, customer_id
    RT->>O: invoke guarded agent
    O->>W: initialize_session()
    W-->>O: state created, version 0

    alt Account details / customer tier
        O->>I: route_to_inventory_agent()
        I-->>O: verified customer facts
        Note over O,P: PolicyAgent is never called
    else Order status / history
        O->>I: route_to_inventory_agent()
        I-->>O: verified order facts
        O->>R: route_to_refund_agent()
        R-->>O: status or eligibility only
        Note over O,R: No refund without an explicit request
    else Explicit return / refund
        O->>I: gather order facts
        O->>P: retrieve applicable policy
        O->>R: decide and initiate if eligible
    else Policy-only question
        O->>P: route_to_policy_agent()
        par Returns retrieval
            P->>P: ReturnsPolicyRetriever
        and Shipping retrieval
            P->>P: ShippingPolicyRetriever
        and Warranty retrieval
            P->>P: WarrantyPolicyRetriever
        end
        P-->>O: grounded policy synthesis
    else Mixed order and policy
        O->>I: gather order facts
        O->>P: retrieve policy context
    else Arithmetic
        O->>O: calculate using full precision
    end

    O->>C: route_to_communication_agent() last
    C->>W: get_full_workflow_context()
    W-->>C: accumulated worker results
    C-->>O: professional final response
    O-->>RT: response
    RT-->>Customer: guarded customer response
```

| Request type | Required route before CommunicationAgent |
|---|---|
| Account details or customer tier | Inventory only; never Policy |
| Order status or history | Inventory, then Refund for evaluation only |
| Policy-only | Policy |
| Explicit return or refund | Inventory, then Policy, then Refund |
| Mixed order and policy | Inventory, then Policy |
| Arithmetic | Orchestrator calculation; no specialist |

Every route initializes the session first and ends with CommunicationAgent. Worker output is persisted between steps instead of being passed only through model prompts.

## Shared WorkflowState

```mermaid
stateDiagram-v2
    [*] --> Initialized: initialize_session / version 0
    Initialized --> InventoryReady: inventory_agent result / version + 1
    Initialized --> PolicyReady: policy_agent result / version + 1
    Initialized --> CommunicationReady: direct-answer path
    InventoryReady --> PolicyReady: mixed or refund route
    InventoryReady --> RefundReady: order-status evaluation
    PolicyReady --> RefundReady: explicit refund route
    InventoryReady --> CommunicationReady: account route
    PolicyReady --> CommunicationReady: policy or mixed route
    RefundReady --> CommunicationReady: order or refund route
    CommunicationReady --> [*]: response delivered
```

```mermaid
erDiagram
    WORKFLOW_STATE {
        string session_id PK
        string customer_id
        string created_at
        number ttl
        number version
        map inventory_agent
        map policy_agent
        map refund_agent
        map communication_agent
    }
```

| Field | Purpose |
|---|---|
| `session_id` | DynamoDB partition key for one workflow |
| `customer_id` | Synthetic customer associated with the request |
| `created_at` / `ttl` | Audit timestamp and automatic 24-hour expiry |
| `version` | Optimistic-lock counter used by conditional writes |
| Worker result columns | Structured facts, policy context, refund decision, and final response |

`_update_workflow_state()` writes only when the stored version equals `expected_version`. On conflict, it reloads the record and retries up to three times. This protects concurrent or delayed worker updates from silently replacing newer state.

AgentCore Memory serves a different scope: `WorkflowStateTable` contains operational state for one workflow, while the seven-day `SESSION_SUMMARY` strategy provides conversational continuity.

## Security and reliability boundaries

- An IAM-authorized caller invokes the runtime; production identity ownership must be enforced outside the model.
- Bedrock Guardrail configuration applies to each agent model invocation.
- The public repository contains placeholders, not deployed identifiers or credentials.
- Logs omit raw prompts and tool values by default; identifiers are pseudonymized for telemetry.
- GitHub delivery uses OIDC and a protected environment, keeping long-lived AWS keys out of CI/CD.
- DynamoDB TTL, AgentCore Memory expiry, log retention, and explicit teardown manage data and cost over the deployment lifecycle.
