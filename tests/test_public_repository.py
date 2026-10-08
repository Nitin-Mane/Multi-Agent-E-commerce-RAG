"""Public-repository safety and evaluator-readiness checks.

These tests intentionally avoid AWS calls so they can run in GitHub Actions
without credentials.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    ".env",
    ".env.example",
    ".gitignore",
    "CONTRIBUTING.md",
    "README.md",
    "SECURITY.md",
    "requirements.txt",
    "requirements-dev.txt",
    "agentcore/agentcore.example.json",
    "agentcore/aws-targets.example.json",
    "docs/ARCHITECTURE.md",
    "docs/EVIDENCE_REPORT.md",
    "docs/CI_CD.md",
    "docs/RUBRIC_MATRIX.md",
    ".github/workflows/validate.yml",
    ".github/workflows/deploy.yml",
    "evidence/transcripts/official-all-tasks-sanitized.txt",
    "evidence/transcripts/official-all-tasks-2026-10-08-original.txt",
    "evidence/transcripts/task3-runtime-guardrail-sanitized.txt",
    "evidence/transcripts/task5-kb-retrieval-sanitized.txt",
    "evidence/transcripts/task6-observability-after-traces-sanitized.txt",
    "evidence/transcripts/trace-generation-2026-10-08-original.txt",
    "evidence/screenshots/aws-agentcore-runtime.jpg",
    "evidence/screenshots/aws-knowledge-bases.jpg",
    "evidence/screenshots/aws-xray-service-map.png",
    "evidence/screenshots/official-tests-120-of-120.png",
}

FORBIDDEN_PATH_PARTS = {
    ".aws",
    ".cache",
    ".venv",
    "__pycache__",
    "build",
    "cdk.out",
    "node_modules",
}

SENSITIVE_PATTERNS = {
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "AWS secret assignment": re.compile(
        r"(?i)aws_secret_access_key\s*[=:]\s*[A-Za-z0-9/+=]{20,}"
    ),
    "AWS session token assignment": re.compile(
        r"(?i)aws_session_token\s*[=:]\s*[A-Za-z0-9/+=]{20,}"
    ),
}


def tracked_paths():
    """Return repository files from a clone or an extracted submission archive."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and ".git" not in path.relative_to(ROOT).parts:
                yield path
        return

    for raw_path in result.stdout.split(b"\0"):
        if raw_path:
            yield ROOT / raw_path.decode("utf-8")


def repository_text_files():
    for path in tracked_paths():
        if not path.is_file():
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".zip"}:
            continue
        if path == Path(__file__).resolve():
            continue
        yield path


class PublicRepositoryTests(unittest.TestCase):
    def test_archive_validation_falls_back_without_git_metadata(self):
        failure = subprocess.CalledProcessError(128, ["git", "ls-files", "-z"])

        with patch.object(subprocess, "run", side_effect=failure):
            paths = set(tracked_paths())

        self.assertIn(ROOT / "README.md", paths)
        self.assertNotIn(ROOT / ".git", paths)

    def test_required_public_repository_files_exist(self):
        missing = sorted(path for path in REQUIRED_FILES if not (ROOT / path).is_file())
        self.assertFalse(missing, f"Missing public-repository files: {missing}")

    def test_readme_contains_evaluator_sections(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        required_headings = {
            "## Architecture",
            "## Quick start",
            "## Testing",
            "## Rubric coverage",
            "## Security and privacy",
            "## Known limitation",
        }
        missing = sorted(heading for heading in required_headings if heading not in readme)
        self.assertFalse(missing, f"README is missing sections: {missing}")

    def test_repository_does_not_publish_credential_bearing_runtime_files(self):
        forbidden_files = {
            "agentcore/agentcore.json",
            "agentcore/aws-targets.json",
        }
        published = sorted(path for path in forbidden_files if (ROOT / path).exists())
        self.assertFalse(
            published,
            f"Private runtime files must not be published: {published}",
        )

    def test_repository_contains_no_credentials(self):
        findings: list[str] = []
        for path in repository_text_files():
            content = path.read_text(encoding="utf-8", errors="replace")
            for label, pattern in SENSITIVE_PATTERNS.items():
                if pattern.search(content):
                    findings.append(f"{path.relative_to(ROOT)}: {label}")
        self.assertFalse(findings, "Sensitive values found:\n" + "\n".join(findings))

    def test_no_generated_or_local_directories_are_published(self):
        findings = []
        for path in tracked_paths():
            relative_parts = set(path.relative_to(ROOT).parts)
            if relative_parts & FORBIDDEN_PATH_PARTS:
                findings.append(str(path.relative_to(ROOT)))
        self.assertFalse(findings, f"Generated/local paths found: {sorted(findings)}")

    def test_runtime_requirements_cover_imported_packages(self):
        requirements_path = ROOT / "requirements.txt"
        self.assertTrue(requirements_path.is_file(), "Missing requirements.txt")
        requirements = requirements_path.read_text(encoding="utf-8").lower()
        for package in ("boto3", "bedrock-agentcore", "strands-agents", "python-dotenv"):
            self.assertIn(package, requirements, f"Missing runtime dependency: {package}")

    def test_submission_uses_original_evidence_only(self):
        """Generated terminal renderings must never be presented as screenshots."""
        documentation = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "README.md", ROOT / "docs" / "EVIDENCE_REPORT.md")
        )
        forbidden_references = {
            "official-tests-120-of-120-summary.png",
            "official-tests-120-of-120-summary-redacted.png",
            "Rendered 120/120 result summary",
            "presentation rendering",
        }
        findings = sorted(
            reference for reference in forbidden_references if reference in documentation
        )
        self.assertFalse(
            findings,
            f"Generated evidence references must be removed: {findings}",
        )

    def test_readme_uses_the_architecture_cover(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "![NovaMart multi-agent customer-support architecture](diagrams/architecture-overview.png)",
            readme,
            "The repository cover must remain visible in the README.",
        )


if __name__ == "__main__":
    unittest.main()
