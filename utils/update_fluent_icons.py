# coding: utf-8
"""Download / update the Fluent UI System Icons font and its license.

Downloads ``FluentSystemIcons-Regular.ttf`` and the matching ``LICENSE``
from the microsoft/fluentui-system-icons repository into
``resources/fonts/``. Each file is skipped when the local copy already
matches the remote content (SHA-256), so repeated runs are cheap and
"up to date".

Pure stdlib (no dependencies), works on any Python 3.11+.

Usage:
    python utils/update_fluent_icons.py
    uv run python utils/update_fluent_icons.py
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

#: The tag/branch tracked by this script. Bump to pin a release tag
#: (e.g. ``refs/tags/v2.7.0``) or keep ``main`` for bleeding-edge.
FONT_BRANCH = "refs/heads/main"

ROOT = Path(__file__).resolve().parent.parent

#: TrueType font magic (scalable TrueType / OpenType outlines).
_TTF_SIGNATURES = (b"\x00\x01\x00\x00", b"true", b"ttcf")

#: Size cap (100 MB) as a sanity guard against a broken redirect/HTML.
MAX_BYTES = 100 * 1024 * 1024


def _url(path: str) -> str:
    """Build the canonical (github.com/.../raw) URL for a repo file."""
    return f"https://github.com/microsoft/fluentui-system-icons/raw/{FONT_BRANCH}/{path}"


def _fallback_url(path: str) -> str:
    """Build the direct raw.githubusercontent.com fallback URL."""
    return (
        "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/"
        f"{FONT_BRANCH}/{path}"
    )


#: Everything the updater keeps in sync: repo file -> local destination,
#: plus an optional content validator (bytes) -> bool.
ASSETS = (
    {
        "name": "font",
        "repo_path": "fonts/FluentSystemIcons-Regular.ttf",
        "local_path": ROOT / "resources" / "fonts" / "FluentSystemIcons-Regular.ttf",
        "validator": lambda data: data.startswith(_TTF_SIGNATURES),
        "error_msg": "downloaded data is not a TrueType font",
    },
    {
        "name": "license",
        "repo_path": "LICENSE",
        "local_path": ROOT / "resources" / "fonts" / "LICENSE",
        "validator": lambda data: (
            data.lstrip().startswith(b"MIT License")
            or data.lstrip().startswith(b"Copyright")
        ),
        "error_msg": "downloaded data is not the expected license text",
    },
)


def sha256(path: Path) -> str:
    """Return the hex SHA-256 of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(repo_path: str, label: str) -> bytes:
    """Download a repo file, trying the canonical then fallback URL."""
    last_error: Exception | None = None
    for url in (_url(repo_path), _fallback_url(repo_path)):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Symplify-font-updater/1.0",
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(request, timeout=60) as resp:
                data = resp.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError(f"response exceeds {MAX_BYTES} bytes")
            return data
        except Exception as e:  # noqa: BLE001 - report and try next URL
            last_error = e
    raise RuntimeError(f"failed to download {label} from both URLs: {last_error}")


def _sync_asset(asset: dict) -> bool:
    """Sync one asset, returning True if it was written/unchanged.

    Returns False on a validation failure so main() can abort early.
    """
    name = asset["name"]
    local = asset["local_path"]
    print(f"Fetching {name}: {_url(asset['repo_path'])}")
    data = _download(asset["repo_path"], name)

    if not asset["validator"](data):
        print(
            f"ERROR: {asset['error_msg']} "
            f"(first bytes {data[:16]!r}). Refusing to overwrite {local}.",
            file=sys.stderr,
        )
        return False

    local.parent.mkdir(parents=True, exist_ok=True)
    new_hash = hashlib.sha256(data).hexdigest()

    if local.exists() and sha256(local) == new_hash:
        print(f"  Already up to date: {local} ({len(data):,} bytes)")
        return True

    tmp = local.with_suffix(local.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(local)
    print(f"  Updated: {local} ({len(data):,} bytes)")
    print(f"    sha256: {new_hash}")
    return True


def main() -> int:
    """Download/update all assets, returning a process exit code."""
    for asset in ASSETS:
        if not _sync_asset(asset):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
