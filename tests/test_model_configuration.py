"""Tests for rubric defaults and lab-safe model overrides."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ModelConfigurationTests(unittest.TestCase):
    def test_required_claude_models_remain_the_defaults(self) -> None:
        source = (ROOT / "config.py").read_text(encoding="utf-8")

        self.assertIn("us.anthropic.claude-haiku-4-5-20251001-v1:0", source)
        self.assertIn("us.anthropic.claude-sonnet-4-5-20250929-v1:0", source)

    def test_environment_can_select_an_accessible_evidence_model(self) -> None:
        source = " ".join((ROOT / "config.py").read_text(encoding="utf-8").split())

        self.assertIn("ORCHESTRATOR_MODEL_ID = os.environ.get(", source)
        self.assertIn("WORKER_MODEL_ID = os.environ.get(", source)


if __name__ == "__main__":
    unittest.main()
