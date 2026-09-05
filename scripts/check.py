"""Run the full quality gate locally, mirroring the CI gate exactly."""

from __future__ import annotations

import subprocess
import sys

_STEPS: tuple[tuple[str, list[str]], ...] = (
    ("ruff format", ["ruff", "format", "--check", "."]),
    ("ruff check", ["ruff", "check", "."]),
    ("mypy", ["mypy"]),
    ("pytest", ["coverage", "run", "-m", "pytest"]),
    ("coverage", ["coverage", "report"]),
    ("pip-audit", ["pip-audit"]),
)


def main() -> int:
    """Run each gate step in order, stopping at the first failure."""
    for name, command in _STEPS:
        print(f"==> {name}")
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            print(f"FAILED: {name}")
            return result.returncode
    print("All gate steps passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
