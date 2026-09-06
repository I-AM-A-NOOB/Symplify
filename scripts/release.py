# coding: utf-8
"""Bump Symplify's version (SemVer) and keep the two sources in sync.

Usage (from the repo root):

    uv run python scripts/release.py patch          # 0.1.0 -> 0.1.1
    uv run python scripts/release.py minor          # 0.1.0 -> 0.2.0
    uv run python scripts/release.py major          # 0.1.0 -> 1.0.0
    uv run python scripts/release.py 0.3.5          # explicit
    uv run python scripts/release.py minor --tag    # also commit + tag v0.2.0

The authoritative version lives in pyproject.toml; python/version.py is the
runtime copy the About page and About/UI read. Tags named ``vX.Y.Z`` drive
the Windows packaging workflow.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
VERSION_PY = ROOT / "python" / "version.py"
TAG_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def read_version() -> tuple:
    m = TAG_RE.search(PYPROJECT.read_text(encoding="utf-8"))
    if not m:
        sys.exit("pyproject.toml: no `version = \"...\"` found")
    return tuple(int(p) for p in m.group(1).split("."))


def write_pyproject(version: str) -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    text = TAG_RE.sub(f'version = "{version}"', text, count=1)
    PYPROJECT.write_text(text, encoding="utf-8")


def write_version_py(version: str) -> None:
    VERSION_PY.write_text(
        '# coding: utf-8\n'
        '"""Symplify version — kept in sync with pyproject.toml by\n'
        '``scripts/release.py`` (pyproject remains the canonical source)."""\n\n'
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )


def bump(major: int, minor: int, patch: int, part: str) -> tuple:
    if part == "patch":
        return (major, minor, patch + 1)
    if part == "minor":
        return (major, minor + 1, 0)
    if part == "major":
        return (major + 1, 0, 0)
    sys.exit(f"unknown bump kind: {part}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "version",
        help="'patch' | 'minor' | 'major', or an explicit SemVer like 0.3.5",
    )
    parser.add_argument("--tag", action="store_true",
                        help="commit and tag v<version> after bumping")
    args = parser.parse_args()

    cur = read_version()
    if re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        new = tuple(int(p) for p in args.version.split("."))
    else:
        new = bump(*cur, args.version)

    # Never go backwards by accident.
    if new <= cur:
        sys.exit(f"version not increased: {cur} -> {new}")

    version_str = ".".join(str(p) for p in new)
    write_pyproject(version_str)
    write_version_py(version_str)
    print(f"Bumped {'.'.join(map(str, cur))} -> {version_str}")

    if args.tag:
        tag = f"v{version_str}"
        subprocess.run(["git", "add", str(PYPROJECT), str(VERSION_PY)], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"Bump version to {version_str}"],
                       cwd=ROOT, check=True)
        subprocess.run(["git", "tag", tag], cwd=ROOT, check=True)
        print(f"Committed and tagged {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
