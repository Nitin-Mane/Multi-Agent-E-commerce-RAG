"""Regression tests for the rubric-defined orchestrator routing contract."""

import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
