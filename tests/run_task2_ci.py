"""Run Udacity's immutable Task 2 checker with a CI-safe exit status.

The supplied rubric script reports some failures in its text output while
still returning process status 0. This wrapper leaves that course file
untouched and converts its published Task 2 score into a reliable CI result.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
EXPECTED_SCORE = "Score: 40/40 pts"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    test_file = Path(__file__).with_name("test_agent.py")
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(test_file), "task2"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
        check=False,
    )

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    combined = ANSI_ESCAPE.sub("", f"{result.stdout}\n{result.stderr}")
    rubric_failed = "FAIL" in combined or EXPECTED_SCORE not in combined
    if result.returncode != 0 or rubric_failed:
        print(
            f"CI validation failed: expected '{EXPECTED_SCORE}' with no FAIL markers.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
