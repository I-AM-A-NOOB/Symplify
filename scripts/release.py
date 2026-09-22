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
UV_LOCK = ROOT / "uv.lock"
TAG_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
#: The lock records the project's own version next to its dependencies.
LOCK_RE = re.compile(r'(name = "symplify"\nversion = )"([^"]+)"')


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


def write_uv_lock(version: str) -> bool:
    """Point the lock's own project entry at ``version``.

    The authoritative version is in pyproject, but a lockfile carries a copy for
    the project itself — and one that is left behind is not merely stale: the
    next ``uv run`` rewrites it, showing up as a change nobody made. Returns
    False when there is no lock or it does not have the expected shape; a lock is
    a build artifact and not worth failing a release over.
    """
    if not UV_LOCK.is_file():
        return False
    text = UV_LOCK.read_text(encoding="utf-8")
    replaced = LOCK_RE.sub(rf'\g<1>"{version}"', text, count=1)
    if replaced == text:
        return False
    UV_LOCK.write_text(replaced, encoding="utf-8")
    return True


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
    elif args.version in ("patch", "minor", "major"):
        new = bump(*cur, args.version)
    else:
        sys.exit(
            f"not a SemVer version or bump kind: {args.version!r} "
            "(expected patch | minor | major | X.Y.Z)"
        )

    # Never go backwards by accident.
    if new <= cur:
        sys.exit(f"version not increased: {cur} -> {new}")

    version_str = ".".join(str(p) for p in new)
    write_pyproject(version_str)
    write_version_py(version_str)
    lock_updated = write_uv_lock(version_str)
    print(f"Bumped {'.'.join(map(str, cur))} -> {version_str}"
          + (" (uv.lock too)" if lock_updated else ""))

    if args.tag:
        tag = f"v{version_str}"
        files = [str(PYPROJECT), str(VERSION_PY)]
        if lock_updated:
            files.append(str(UV_LOCK))
        subprocess.run(["git", "add", *files], cwd=ROOT, check=True)
        # Explicit pathspec: commit only the version files, never whatever else
        # the caller happened to have staged.
        subprocess.run(
            ["git", "commit", "-m", f"Bump version to {version_str}", "--", *files],
            cwd=ROOT, check=True,
        )
        subprocess.run(["git", "tag", tag], cwd=ROOT, check=True)
        print(f"Committed and tagged {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
