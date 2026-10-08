"""Validate reviewer navigation and local image ownership in Markdown docs."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
LOCAL_IMAGE = re.compile(r"!\[[^]]*\]\((?!https?://)([^)]+)\)")
LOCAL_LINK = re.compile(r"(?<!!)\[[^]]+\]\((?!https?://|mailto:)([^)]+)\)")


def local_images(path: Path) -> list[str]:
    """Return local image destinations embedded by one Markdown file."""
    return [match.group(1).split(maxsplit=1)[0] for match in LOCAL_IMAGE.finditer(path.read_text(encoding="utf-8"))]


class DocumentationStructureTests(unittest.TestCase):
    def test_each_review_figure_has_one_canonical_document(self):
        expected = {
            "README.md": ["diagrams/architecture-overview.png"],
            "docs/ARCHITECTURE.md": ["../diagrams/request-flow-scenarios.png"],
            "docs/EVIDENCE_REPORT.md": [
                "../evidence/screenshots/aws-xray-service-map.png",
                "../evidence/screenshots/official-tests-120-of-120.png",
            ],
        }

        actual = {
            path.relative_to(ROOT).as_posix(): local_images(path)
            for path in MARKDOWN_FILES
            if local_images(path)
        }
        self.assertEqual(expected, actual)

    def test_reviewer_facing_relative_links_resolve(self):
        broken: list[str] = []
        for document in MARKDOWN_FILES:
            content = document.read_text(encoding="utf-8")
            destinations = [
                *[match.group(1) for match in LOCAL_IMAGE.finditer(content)],
                *[match.group(1) for match in LOCAL_LINK.finditer(content)],
            ]
            for destination in destinations:
                target = unquote(destination.split("#", 1)[0].split(maxsplit=1)[0])
                if not target:
                    continue
                resolved = (document.parent / target).resolve()
                if not resolved.exists():
                    broken.append(
                        f"{document.relative_to(ROOT).as_posix()} -> {destination}"
                    )

        self.assertFalse(broken, "Broken documentation links:\n" + "\n".join(broken))


if __name__ == "__main__":
    unittest.main()
