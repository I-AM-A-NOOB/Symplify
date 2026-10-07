# coding: utf-8
"""Bump Symplify's version (SemVer) and keep the two sources in sync.

Usage (from the repo root):

    uv run python scripts/release.py patch          # 0.1.0 -> 0.1.1
    uv run python scripts/release.py minor          # 0.1.0 -> 0.2.0
    uv run python scripts/release.py major          # 0.1.0 -> 1.0.0
    uv run python scripts/release.py 0.3.5          # explicit
    uv run python scripts/release.py minor --tag    # also commit + tag v0.2.0
    uv run python scripts/release.py minor --publish  # ... and build, package, publish
                                                      # (the release path — the CI
                                                      # runner cannot build this)

The authoritative version lives in pyproject.toml; python/version.py is the
runtime copy the About page and About/UI read. Tags named ``vX.Y.Z`` drive
the Windows packaging workflow.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
VERSION_PY = ROOT / "python" / "version.py"
UV_LOCK = ROOT / "uv.lock"
TAG_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
#: What `--publish` builds, packages and uploads.
BUILD_DIST = ROOT / "build" / "main.dist"
BUILD_SCRIPT = ROOT / "scripts" / "build_windows.py"
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


# ---------------------------------------------------------------------------
# Publishing: the local build *is* the release path
# ---------------------------------------------------------------------------
# The GitHub runner cannot finish this build — MSVC runs out of heap on sympy's own
# generated C (`polys.polyquinticconst`, 26k lines) even with `--low-memory` and
# `--jobs=1`, while the same commit builds here in about four minutes. So the
# release is made where it can be made, and `gh` publishes it.


def repo_is_dirty() -> bool:
    """True when tracked files differ. A release must come from a committed tree:
    the tag has to describe exactly what was built."""
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout
    return bool(out.strip())


def build_dist() -> None:
    """Run the Nuitka build and insist on the executable that comes out."""
    subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT, check=True)
    exe = BUILD_DIST / "symplify.exe"
    if not exe.is_file():
        sys.exit(f"the build finished without {exe}")
    print(f"Built {exe} ({exe.stat().st_size / 1e6:.0f} MB)")


def make_zip(version: str, dist_dir: Path = BUILD_DIST) -> Path:
    """Zip the distribution the way the workflow used to: one folder, `main.dist/…`.

    ``dist_dir`` is a parameter so this can be exercised without a real build.
    """
    # Under build/, next to the tree it packages: the repository root is not a
    # place for a 100 MB artifact, and build/ is already ignored by git.
    out_dir = ROOT / "build"
    out_dir.mkdir(exist_ok=True)
    archive = shutil.make_archive(str(out_dir / f"symplify-v{version}"), "zip",
                                  root_dir=dist_dir.parent, base_dir=dist_dir.name)
    print(f"Packaged {archive} ({Path(archive).stat().st_size / 1e6:.0f} MB)")
    return Path(archive)


def tag_exists(tag: str) -> bool:
    """True when the local repository has ``tag``, pointed at HEAD.

    The tag has to describe exactly what was built, so a tag that exists but sits on
    another commit is not a release — it is a stale one.
    """
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    tagged = subprocess.run(["git", "rev-list", "-n", "1", tag], cwd=ROOT,
                            capture_output=True, text=True)
    return tagged.returncode == 0 and tagged.stdout.strip() == head


def publish(version: str) -> None:
    """Push the version and the tag, then let `gh` create the Release.

    Network failures are the boring kind of release failure, and they arrive *after*
    the expensive part: the package is made first (so it is ready either way), and a
    push that cannot reach GitHub says what is done, what is not, and the one command
    that finishes it.
    """
    tag = f"v{version}"
    archive = make_zip(version)

    for args in (["git", "push", "origin", "main"], ["git", "push", "origin", tag]):
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            sys.exit(
                f"pushing {args[-1]} failed:\n{detail}\n"
                f"\nNothing was published. The build and {archive.name} are ready, and the"
                f"\ntag is committed locally; when the network is back, finish with:"
                f"\n\n    uv run python scripts/release.py --publish-only\n"
            )

    create = subprocess.run(
        ["gh", "release", "create", tag, str(archive),
         "--title", f"Symplify {version}", "--generate-notes"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if create.returncode:
        text = (create.stderr + create.stdout).strip()
        if "already exists" in text:
            # A previous attempt got as far as the Release but not the asset.
            subprocess.run(["gh", "release", "upload", tag, str(archive), "--clobber"],
                           cwd=ROOT, check=True)
            print(f"Release {tag} already existed; uploaded {archive.name} to it")
            return
        sys.exit(f"`gh release create` failed:\n{text}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "version", nargs="?",
        help="'patch' | 'minor' | 'major', or an explicit SemVer like 0.3.5 "
             "(not needed with --publish-only, which reads it from pyproject)",
    )
    parser.add_argument("--tag", action="store_true",
                        help="commit and tag v<version> after bumping")
    parser.add_argument(
        "--publish-only", action="store_true",
        help="re-run only the publishing half of --publish (no bump, no build): push the "
             "version commit and its tag, package the existing build/main.dist and create "
             "the Release — for a release whose build succeeded but whose push did not",
    )
    parser.add_argument("--publish", action="store_true",
                        help="implies --tag, then build, package and `gh release create` "
                             "(the release path, since the CI runner cannot build this)")
    args = parser.parse_args()

    if args.publish_only:
        if repo_is_dirty():
            sys.exit("working tree is dirty — commit or stash first: a release must "
                     "come from a committed tree")
        version_str = ".".join(str(p) for p in read_version())
        if not tag_exists(f"v{version_str}"):
            sys.exit(f"no v{version_str} tag at HEAD — nothing to finish; run "
                     f"`release.py {version_str} --publish` (or bump) instead")
        publish(version_str)
        return 0

    if args.publish:
        # The tag is what `gh release create` attaches to, so it is not optional.
        args.tag = True
        # Checked before anything is written: a release must be reproducible from
        # the commit the tag points at, and a dirty tree is not that commit.
        if repo_is_dirty():
            sys.exit("working tree is dirty — commit or stash first: a release must "
                     "come from a committed tree")

    if not args.version:
        parser.error("a version is required unless --publish-only is used")

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
    if args.publish:
        # Build first, publish second: the tag is local until the artifact exists,
        # so a failed build leaves nothing remote to clean up.
        build_dist()
        publish(version_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
