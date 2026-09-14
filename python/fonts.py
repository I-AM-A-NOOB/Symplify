# coding: utf-8
"""Font discovery and preference-list handling (pure Python, zero Qt).

Two jobs the settings page needs:

* **Parsing a preference list.** A row stores a comma-separated list of families
  plus generic keywords; :func:`split_families` and :func:`expand_keyword` turn
  that into the ordered family names Qt resolves characters against.
* **Finding fonts that can typeset maths.** ziamath (via ziafont) opens a font
  *file* and requires a ``MATH`` typesetting table: a font without one raises
  ``ValueError: Font has no MATH table!``, and a collection (``.ttc``) is
  unreadable outright (``UnicodeDecodeError``). :func:`math_font_choices` lists
  only what can really render, which fontTools decides by reading each file's
  table directory, and :func:`math_font_path` extracts a collection member into a
  scratch ``.ttf`` when that is the only way to get a usable file.

Nothing here renders anything or talks to Qt — the Qt-side work (resolving which
families are installed, measuring glyph coverage) lives in the settings
viewmodel, so this module stays testable without a QApplication.
"""

import os
import re
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: Families tried, in order, for code text (monospace preferred). Picked so the
#: Windows, macOS and Linux entries cover the same ground; the generic keyword
#: last is expanded by :data:`GENERIC_EXPANSIONS`.
DEFAULT_CODE_FAMILY = (
    "Cascadia Mono, Consolas, SF Mono, Menlo, Monaco, "
    "DejaVu Sans Mono, Liberation Mono, Courier New, monospace"
)

#: Families tried, in order, for the keyboard panel (serif preferred — the
#: mathematical glyphs read better in a serif face). Cambria leads because it is
#: the only common candidate covering *all* of "∞ √ ∛ ≤ ≥ π φ γ ∫ ∑ ± × ÷ ∂ ∈".
DEFAULT_KEYBOARD_FAMILY = (
    "Cambria, Georgia, Times New Roman, Palatino, "
    "DejaVu Serif, Liberation Serif, serif"
)

#: Generic keywords a user may type, expanded into real families to try.
GENERIC_EXPANSIONS: Dict[str, Tuple[str, ...]] = {
    "monospace": (
        "Cascadia Mono", "Consolas", "SF Mono", "Menlo", "Monaco",
        "DejaVu Sans Mono", "Liberation Mono", "Courier New", "Noto Sans Mono",
    ),
    "serif": (
        "Cambria", "Georgia", "Times New Roman", "Palatino",
        "DejaVu Serif", "Liberation Serif", "Noto Serif", "Songti SC",
    ),
    "sans-serif": (
        "Segoe UI", "Helvetica Neue", "DejaVu Sans", "Liberation Sans",
        "Noto Sans",
    ),
}

#: Suffixes that can hold a usable font (a collection is read, then extracted).
_FONT_SUFFIXES = (".ttf", ".otf", ".ttc", ".otc")

#: Characters code text needs. The keyboard's own symbols appear in expressions
#: too (a user types `√` from the panel, which inserts `sqrt(`), so the
#: arithmetic and comparison signs are what a code font has to cover.
CODE_GLYPHS = "0123456789+-*/^=<>()[]{}.,;:%|!_"

_MATH_FONT_CACHE_DIRNAME = "symplify-fonts"


def split_families(text: str) -> List[str]:
    """Parse a comma-separated preference list into family names, in order."""
    return [part.strip() for part in str(text or "").split(",") if part.strip()]


def expand_keyword(name: str) -> Tuple[str, ...]:
    """``name`` as candidate families: generic keywords expand, others pass through."""
    return GENERIC_EXPANSIONS.get(name.strip().casefold(), (name,))


def font_directories() -> List[Path]:
    """The platform's font directories, in the order a font would be found.

    Mirrors what ziafont searches (``ziafont/findfont.py``) plus the per-user
    directories, so a font listed here is one ziamath can actually open.
    """
    home = Path.home()
    if sys.platform == "win32":
        dirs = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.insert(0, Path(local) / "Microsoft" / "Windows" / "Fonts")
        return [d for d in dirs if d.is_dir()]

    if sys.platform == "darwin":
        dirs = [
            home / "Library" / "Fonts",
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path("/Network/Library/Fonts"),
        ]
        return [d for d in dirs if d.is_dir()]

    dirs = [
        home / ".local" / "share" / "fonts",
        home / ".fonts",
        Path("/usr/local/share/fonts"),
        Path("/usr/share/fonts"),
    ]
    return [d for d in dirs if d.is_dir()]


def _font_files() -> List[Path]:
    """Every font file in the platform font directories (recursive)."""
    files: List[Path] = []
    for directory in font_directories():
        for path, _dirs, names in os.walk(directory):
            for name in names:
                if name.lower().endswith(_FONT_SUFFIXES):
                    files.append(Path(path) / name)
    return files


def _math_families(path: Path) -> List[str]:
    """Family names in ``path`` whose font carries a ``MATH`` table.

    A broken or unreadable file yields an empty list rather than raising: font
    directories routinely hold files that fontTools cannot parse.
    """
    try:
        from fontTools.ttLib import TTCollection, TTFont

        if path.suffix.lower() in (".ttc", ".otc"):
            fonts = TTCollection(path, lazy=True).fonts
        else:
            fonts = [TTFont(path, lazy=True, fontNumber=0)]
        names: List[str] = []
        for font in fonts:
            if "MATH" not in font:
                continue
            family = font["name"].getDebugName(1)
            if family:
                names.append(family)
        return names
    except Exception:
        return []


def _is_collection(path: Path) -> bool:
    return path.suffix.lower() in (".ttc", ".otc")


@lru_cache(maxsize=1)
def math_font_choices() -> Tuple[Dict[str, Any], ...]:
    """System fonts that can render math, as ``{family, path, collection}``.

    Cached: the scan reads the table directory of every installed font (~0.2 s
    for 500 files here), so it must not run per query. Only fonts with a MATH
    table are returned — offering the others would produce blank output, because
    ziamath fails on them instead of substituting a font.
    """
    choices: List[Dict[str, Any]] = []
    seen = set()
    for path in sorted(_font_files()):
        for family in _math_families(path):
            key = family.casefold()
            if key in seen:
                continue
            seen.add(key)
            choices.append({
                "family": family,
                "path": str(path),
                "collection": _is_collection(path),
            })
    return tuple(sorted(choices, key=lambda c: c["family"].casefold()))


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower() or "font"


def _extract_collection(path: Path, family: str) -> Optional[str]:
    """Write ``family`` out of a ``.ttc`` as a standalone ``.ttf`` (cached).

    ziafont opens a font file as a single font and cannot read a collection, so
    a MATH font that only exists inside one (Cambria Math on Windows) has to be
    extracted before ziamath can use it. The copy goes into a scratch folder
    under the system temp directory, is written once per file, and is reused
    afterwards — the font itself never changes.
    """
    cache = Path(tempfile.gettempdir()) / _MATH_FONT_CACHE_DIRNAME
    target = cache / f"{_slug(family)}.ttf"
    if target.is_file() and target.stat().st_size > 0:
        return str(target)
    try:
        from fontTools.ttLib import TTCollection

        for font in TTCollection(path, lazy=False).fonts:
            if "MATH" in font and font["name"].getDebugName(1) == family:
                cache.mkdir(parents=True, exist_ok=True)
                font.save(target)
                return str(target)
    except Exception:
        return None
    return None


def math_font_path(family: str) -> Optional[str]:
    """The file to hand ziamath for ``family``; ``None`` means "use the default".

    An empty or unknown family falls back to the default — ziamath's bundled
    STIX Two Math — which is also the first choice in the UI.
    """
    name = str(family or "").strip()
    if not name:
        return None
    for choice in math_font_choices():
        if choice["family"].casefold() != name.casefold():
            continue
        if choice["collection"]:
            return _extract_collection(Path(choice["path"]), choice["family"])
        return str(choice["path"])
    return None
