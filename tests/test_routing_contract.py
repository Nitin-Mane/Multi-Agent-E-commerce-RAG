"""Regression tests for the rubric-defined orchestrator routing contract."""

import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

import src.agent_orchestrator as orchestrator_module
from botocore.exceptions import ClientError


ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_SOURCE = ROOT / "src" / "agent_orchestrator.py"


def _source() -> str:
    return " ".join(ORCHESTRATOR_SOURCE.read_text(encoding="utf-8").split())


class OrchestratorRoutingContractTests(unittest.TestCase):
    def test_account_and_tier_questions_use_inventory_and_never_policy(self) -> None:
        source = _source()

        self.assertIn("For account details or customer-tier questions", source)
        self.assertIn("call Inventory, never Policy, then Communication", source)

    def test_order_status_uses_refund_without_starting_refund(self) -> None:
        source = _source()

        self.assertIn(
            "For order status or order history, call Inventory, then Refund, then "
            "Communication",
            source,
        )
        self.assertIn("Refund evaluates status or eligibility only", source)
        self.assertIn(
            "do not initiate a refund unless the customer explicitly requests one",
            source,
        )

    def test_communication_remains_the_final_worker(self) -> None:
        self.assertIn("Communication must always be the final worker", _source())

    def test_evidence_runner_initializes_state_before_model_routing(self) -> None:
        events: list[str] = []

        def create_state(session_id: str, customer_id: str) -> dict:
            events.append("state_initialized")
            return {"session_id": session_id, "customer_id": customer_id}

        def invoke_agent(prompt: str) -> str:
            self.assertEqual(["state_initialized"], events)
            events.append("agent_invoked")
            return "completed"

        trace = Mock()
        trace.trace_request.return_value = nullcontext()

        with (
            patch.object(
                orchestrator_module,
                "TEST_CASES",
                [("CUST-TEST", "What is my return policy?")],
            ),
            patch.object(orchestrator_module, "setup_logging"),
            patch.object(orchestrator_module, "build_agent_graph", return_value=invoke_agent),
            patch.object(orchestrator_module, "_create_workflow_state", side_effect=create_state),
            patch.object(orchestrator_module, "tracer", trace),
            patch.object(orchestrator_module, "print_trace_hint"),
            patch.object(orchestrator_module, "flush_logs"),
            patch.object(orchestrator_module.uuid, "uuid4", return_value="12345678-test"),
            patch("builtins.print"),
        ):
            orchestrator_module.run_test_scenarios()

        self.assertEqual(["state_initialized", "agent_invoked"], events)

    def test_workflow_state_creation_is_idempotent_for_the_same_customer(self) -> None:
        table = Mock()
        table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}},
            "PutItem",
        )
        table.get_item.return_value = {
            "Item": {
                "session_id": "session-1",
                "customer_id": "customer-1",
                "version": 2,
            }
        }

        with (
            patch.dict(
                orchestrator_module.config.__dict__,
                {"WORKFLOW_STATE_TABLE": "workflow-state"},
            ),
            patch.object(orchestrator_module.dynamodb, "Table", return_value=table),
        ):
            state = orchestrator_module._create_workflow_state(
                "session-1", "customer-1"
            )

        self.assertEqual("session-1", state["session_id"])
        self.assertEqual(2, state["version"])


if __name__ == "__main__":
    unittest.main()
