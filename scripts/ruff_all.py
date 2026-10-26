"""Run Ruff over every Python file in the project.

Useful when a check needs to cover the whole tree, not only `python/` — tests,
`scripts/`, `main.py` and any future tooling are included. Generated and
third-party directories are skipped.

Arguments are passed through to `ruff check`:

    uv run python scripts/ruff_all.py
    uv run python scripts/ruff_all.py --select UP
    uv run python scripts/ruff_all.py --select UP --fix
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Directories that never contain project-owned Python.
SKIP_DIRS = {
    ".git",
    ".idea",
    ".venv",
    ".vs",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


def python_files() -> list[Path]:
    """Every project-owned .py file, sorted for stable output."""
    return sorted(
        path for path in ROOT.rglob("*.py")
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    )


def ruff_command() -> list[str]:
    """Locate Ruff, falling back to the environment's `uv run ruff`."""
    executable = shutil.which("ruff")
    if executable:
        return [executable]
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "ruff"]
    raise SystemExit("ruff was not found; install it or run this through `uv`")


def main(argv: list[str]) -> int:
    files = python_files()
    if not files:
        print("No Python files found.")
        return 0
    command = ruff_command() + [
        "check", "--target-version=py311", *argv, *map(str, files)
    ]
    print(f"Ruff: {len(files)} file(s)")
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
