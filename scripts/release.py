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
runtime copy the About page and About/UI read. The packaging half (``--publish``,
``--publish-only``) makes the two downloads a release carries, both named for the
platform and the architecture they are for:

* ``Symplify-v<version>-<platform>-<arch>-portable.zip`` — the Nuitka tree inside
  a top-level ``Symplify/`` folder, plus the empty ``data/`` that makes it
  portable (python/settings.py reads the settings next to the exe when that
  folder exists).
* ``Symplify-v<version>-<platform>-<arch>-setup.exe`` — ``installer/Symplify.iss``
  compiled by Inno Setup 7, which installs that same tree and *not* the ``data``
  folder, so an installed copy keeps its settings in the OS config directory.
"""

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
VERSION_PY = ROOT / "python" / "version.py"
UV_LOCK = ROOT / "uv.lock"
TAG_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
#: What `--publish` builds, packages and uploads.
BUILD_DIST = ROOT / "build" / "main.dist"
BUILD_SCRIPT = ROOT / "scripts" / "build_windows.py"
#: The Inno Setup script the setup executable is compiled from.
INSTALLER_SCRIPT = ROOT / "installer" / "Symplify.iss"
#: The lock records the project's own version next to its dependencies.
LOCK_RE = re.compile(r'(name = "symplify"\nversion = )"([^"]+)"')

#: Where every artefact is written: next to the tree it is made from, because
#: the repository root is no place for a 100 MB download and `build/` is already
#: ignored by git.
BUILD_DIR = ROOT / "build"

#: The platform the artefacts are for. Windows is the only one that ships today;
#: it is a constant rather than ``sys.platform`` so the name on a download is the
#: name of the thing it runs on, and so a future `linux` / `macos` build is a
#: value here plus a packaging step rather than a rename of every file.
PLATFORM = "windows"

#: ``platform.machine()`` -> the token in the file name. Windows reports ``AMD64``
#: for x64, which is what ``amd64`` means on Linux; ``x64`` is what Windows, the
#: DLLs in the build (``libcrypto-3-x64.dll``) and Inno Setup (``x64compatible``)
#: call it, so that is the spelling a download carries.
ARCH_TOKENS = {
    "AMD64": "x64",
    "X86_64": "x64",
    "ARM64": "arm64",
    "ARM64EC": "arm64",
    "X86": "x86",
    "I386": "x86",
    "I686": "x86",
}

#: Folder name inside the portable archive. Nuitka names the folder after the
#: entry script (``main.dist``), which is a build detail; what a user extracts
#: should be the application's own folder.
PORTABLE_ROOT = "Symplify"
#: Empty folder inside the portable archive that switches the app to portable
#: mode — `resolve_config_dir` in python/settings.py keeps the settings next to
#: the exe when it exists. The installer deliberately does not create it.
PORTABLE_DATA_DIR = "data"


def host_arch() -> str:
    """The architecture of this machine, spelled for a file name."""
    machine = platform.machine().upper()
    token = ARCH_TOKENS.get(machine)
    if token is None:
        sys.exit(f"unknown architecture {machine!r}: add it to ARCH_TOKENS")
    return token


def artifact_name(version: str, arch: str, kind: str, suffix: str) -> str:
    """``Symplify-v1.2.3-windows-x64-<kind><suffix>``."""
    return f"Symplify-v{version}-{PLATFORM}-{arch}-{kind}{suffix}"


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


def make_zip(version: str, arch: str, dist_dir: Path = BUILD_DIST) -> Path:
    """Package the distribution as the *portable* download.

    Two things in here are the point of the archive:

    * everything sits under one top-level ``Symplify/`` folder — Nuitka's
      ``main.dist`` is a build detail and ``Symplify`` is what the user's
      extraction, their shortcuts and the folder they move around should say;
    * that folder carries an **empty** ``data/``, which is exactly the test
      ``resolve_config_dir`` (python/settings.py) makes for portable mode. So the
      settings land next to the exe and nothing outside the extracted folder is
      touched. The installer must not ship this folder (see installer/Symplify.iss).

    ``dist_dir`` is a parameter so this can be exercised without a real build.
    """
    if not dist_dir.is_dir():
        sys.exit(f"nothing to package: {dist_dir} does not exist (build it first)")

    BUILD_DIR.mkdir(exist_ok=True)
    archive = BUILD_DIR / artifact_name(version, arch, "portable", ".zip")
    archive.unlink(missing_ok=True)

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _dirnames, filenames in os.walk(dist_dir):
            folder = Path(dirpath)
            relative = folder.relative_to(dist_dir)
            arc_dir = PORTABLE_ROOT if relative == Path(".") \
                else f"{PORTABLE_ROOT}/{relative.as_posix()}"
            # The folder itself: an empty directory survives extraction only if
            # it has an entry of its own, which is how the `data/` below works
            # and what keeps a pruned-but-empty Qt directory from disappearing.
            # (write() appends the trailing slash for a directory.)
            zf.write(folder, arc_dir)
            for name in filenames:
                zf.write(folder / name, f"{arc_dir}/{name}")
        # mkdir(), not writestr(): a directory entry that says it is one.
        zf.mkdir(f"{PORTABLE_ROOT}/{PORTABLE_DATA_DIR}")

    print(f"Packaged {archive.name} ({archive.stat().st_size / 1e6:.0f} MB)")
    return archive


def _iscc_candidates() -> list:
    """``ISCC.exe`` installations to look at, newest Inno Setup first.

    The per-user directory first because that is where the Inno Setup installer
    puts it by default, and both ``Program Files`` next for a machine-wide one.
    The version is in the folder name (``Inno Setup 7``), so sorting on it picks
    the newer compiler — which matters when 6 and 7 are installed side by side:
    the script uses ``SetupArchitecture`` and ``WizardStyle=… dynamic``, neither
    of which Inno Setup 6 understands.
    """
    roots = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "Programs")
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if base:
            roots.append(Path(base))
    found = [path for root in roots for path in root.glob("Inno Setup */ISCC.exe")]
    return sorted(found, key=lambda path: path.parent.name, reverse=True)


def find_iscc() -> Path:
    """The Inno Setup compiler to build the installer with.

    ``ISCC`` in the environment wins (a machine with several installs, or one
    somewhere unusual), then an installed Inno Setup, then ``PATH``.
    """
    override = os.environ.get("ISCC")
    if override:
        path = Path(override)
        if not path.is_file():
            sys.exit(f"ISCC={override} does not exist")
        return path

    candidates = _iscc_candidates()
    if candidates:
        return candidates[0]

    on_path = shutil.which("iscc")
    if on_path:
        return Path(on_path)

    sys.exit(
        "no Inno Setup found — install Inno Setup 7 (winget install "
        "JRSoftware.InnoSetup.7) or set ISCC to its ISCC.exe"
    )


def make_installer(version: str, arch: str, dist_dir: Path = BUILD_DIST) -> Path:
    """Compile ``installer/Symplify.iss`` into the setup executable.

    Every value the script needs is passed as a ``/D`` define, so the version is
    the one in pyproject.toml and the architecture is the one of the build that
    was actually made — nothing in the script is edited between releases.
    """
    if not dist_dir.is_dir():
        sys.exit(f"nothing to install: {dist_dir} does not exist (build it first)")
    if not INSTALLER_SCRIPT.is_file():
        sys.exit(f"missing installer script: {INSTALLER_SCRIPT}")

    iscc = find_iscc()
    BUILD_DIR.mkdir(exist_ok=True)
    setup = BUILD_DIR / artifact_name(version, arch, "setup", ".exe")
    setup.unlink(missing_ok=True)

    print(f"Compiling {INSTALLER_SCRIPT.name} with {iscc}")
    subprocess.run(
        [
            str(iscc),
            f"/DMyAppVersion={version}",
            f"/DPlatform={PLATFORM}",
            f"/DArch={arch}",
            f"/DSourceDir={dist_dir}",
            f"/DOutputDir={BUILD_DIR}",
            str(INSTALLER_SCRIPT),
        ],
        cwd=ROOT,
        check=True,
    )
    if not setup.is_file():
        sys.exit(f"{iscc.name} finished without producing {setup}")

    print(f"Built {setup.name} ({setup.stat().st_size / 1e6:.0f} MB)")
    return setup


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
    the expensive part: the downloads are made first (so they are ready either way),
    and a push that cannot reach GitHub says what is done, what is not, and the one
    command that finishes it.
    """
    tag = f"v{version}"
    arch = host_arch()
    assets = [make_zip(version, arch), make_installer(version, arch)]

    for args in (["git", "push", "origin", "main"], ["git", "push", "origin", tag]):
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            names = " and ".join(asset.name for asset in assets)
            sys.exit(
                f"pushing {args[-1]} failed:\n{detail}\n"
                f"\nNothing was published. The build and {names} are ready, and the"
                f"\ntag is committed locally; when the network is back, finish with:"
                f"\n\n    uv run python scripts/release.py --publish-only\n"
            )

    create = subprocess.run(
        ["gh", "release", "create", tag, *[str(asset) for asset in assets],
         "--title", f"Symplify {version}", "--generate-notes"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if create.returncode:
        text = (create.stderr + create.stdout).strip()
        if "already exists" in text:
            # A previous attempt got as far as the Release but not the assets.
            subprocess.run(["gh", "release", "upload", tag,
                            *[str(asset) for asset in assets], "--clobber"],
                           cwd=ROOT, check=True)
            print(f"Release {tag} already existed; uploaded "
                  + " and ".join(asset.name for asset in assets) + " to it")
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
             "version commit and its tag, package the existing build/main.dist into the "
             "portable zip and the setup executable, and create the Release — for a "
             "release whose build succeeded but whose push did not",
    )
    parser.add_argument("--publish", action="store_true",
                        help="implies --tag, then build, package (portable zip + Inno Setup "
                             "installer) and `gh release create` (the release path, since "
                             "the CI runner cannot build this)")
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
