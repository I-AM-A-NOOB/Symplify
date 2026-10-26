"""Keyboard layout helpers for the QML app.

Loads the keyboard config YAML and flattens each tab's grid into the keys QML
places with GridLayout attached properties. A key carries three strings:

- ``label`` — the plain-text label, also the fallback/accessibility text;
- ``latex`` — optional LaTeX for a typeset keycap; empty means use ``label``;
- ``insert`` — what the key types.

The label and insert differ where the glyph and the function do (``√`` shows,
``sqrt`` types); ``latex`` is a third, optional rendering hint.
"""

from itertools import count
from pathlib import Path
from typing import Any

import yaml

KEYBOARD_CONFIG_PATH = Path(__file__).resolve().parent / "keyboard_config.yaml"

#: Folder under the settings directory for user copies of the layout.
KEYBOARD_DIRNAME = "keyboards"

#: Files the switcher offers; both spellings are valid YAML.
KEYBOARD_SUFFIXES = (".yaml", ".yml")

#: Minimal numeric keypad used when the YAML config cannot be loaded.
FALLBACK_GRID: list[list[str]] = [
    ["7", "8", "9", "/"],
    ["4", "5", "6", "*"],
    ["1", "2", "3", "-"],
    ["0", ".", "=", "+"],
]


def _flatten_cell(cell: Any) -> dict[str, str] | None:
    """One grid cell as ``{'label', 'latex', 'insert'}``, or None when empty.

    A cell is either a plain string — the common case, where the key shows and
    types the same text — or a mapping. ``label`` is the plain fallback,
    ``latex`` an optional typeset keycap, and ``insert`` what the key types.
    A mapping may omit ``label`` (it then follows ``insert``) or ``latex`` (it
    then uses the label).
    """
    if isinstance(cell, str):
        return {"label": cell, "latex": "", "insert": cell} if cell else None
    if isinstance(cell, dict):
        insert = str(cell.get("insert") or "")
        label = str(cell.get("label") or "")
        if not insert and not label:
            return None
        return {
            "label": label or insert,
            "latex": str(cell.get("latex") or ""),
            "insert": insert or label,
        }
    return None


def _flatten_grid(grid: list[list[Any]]) -> dict[str, Any]:
    """Flatten a 2D grid of key cells into columns/keys."""
    columns = max((len(row) for row in grid), default=1)
    keys: list[dict[str, Any]] = []
    for row_idx, row in enumerate(grid):
        for col_idx, cell in enumerate(row):
            flattened = _flatten_cell(cell)
            if flattened is not None:
                keys.append({**flattened, "row": row_idx, "col": col_idx})
    return {"columns": columns, "keys": keys}


def keyboard_dir(config_dir: Path) -> Path:
    """The user keyboard folder for a settings directory."""
    return Path(config_dir) / KEYBOARD_DIRNAME


def keyboard_files(directory: Path) -> list[Path]:
    """YAML files in a keyboard folder, by case-insensitive filename."""
    try:
        entries = Path(directory).iterdir()
    except OSError:
        return []
    return sorted(
        (path for path in entries
         if path.is_file() and path.suffix.lower() in KEYBOARD_SUFFIXES),
        key=lambda path: path.name.casefold(),
    )


def _tabs_from_path(path: Path) -> list[dict[str, Any]]:
    """Parse one layout file; an unusable file contributes no tabs."""
    try:
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except (OSError, UnicodeError, yaml.YAMLError):
        return []
    if not isinstance(config, dict) or not config:
        return []

    tabs: list[dict[str, Any]] = []
    for route_key, tab in config.items():
        if not isinstance(tab, dict):
            continue  # a malformed tab contributes no keys
        grid = tab.get("grid")
        descriptor = {
            "key": route_key,
            "title": tab.get("title", route_key),
            **_flatten_grid(grid if isinstance(grid, list) else []),
        }
        shift_grid = tab.get("shiftGrid")
        if isinstance(shift_grid, list) and shift_grid:
            shifted = _flatten_grid(shift_grid)
            descriptor["shiftColumns"] = shifted["columns"]
            descriptor["shiftKeys"] = shifted["keys"]
        tabs.append(descriptor)
    return tabs


def _fallback_tabs() -> list[dict[str, Any]]:
    return [{"key": "basic", "title": "Basic", **_flatten_grid(FALLBACK_GRID)}]


def load_keyboard_layout(
    path: Path | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Load a layout and report the fallback when its file could not be used.

    ``path=None`` means the packaged default. A selected custom file that is
    missing or malformed falls back to that default, not to the tiny numeric
    keypad; only a damaged installation reaches the numeric keypad. The returned
    message is empty on success. It names the failed file — not a full path — so
    the log, dialog and settings row can all say which keyboard was rejected.

    Each tab becomes
    ``{"title", "columns", "keys": [{label, latex, insert, row, col}]}``.
    A tab with an optional ``shiftGrid`` also carries ``shiftColumns`` and
    ``shiftKeys`` in the same shape; the QML Shift toggle selects that layer.
    Tabs without one keep using ``keys`` when Shift is on, so the modifier is
    available everywhere but only changes the pages that define a layer.
    """
    custom = Path(path) if path is not None else None
    if custom is not None:
        tabs = _tabs_from_path(custom)
        if tabs:
            return tabs, ""
        default = _tabs_from_path(KEYBOARD_CONFIG_PATH)
        if default:
            return default, (
                f"Could not load {custom.name}; using the built-in keyboard."
            )
        return _fallback_tabs(), (
            f"Could not load {custom.name} or the built-in keyboard; "
            "using the numeric keypad."
        )

    tabs = _tabs_from_path(KEYBOARD_CONFIG_PATH)
    if tabs:
        return tabs, ""
    return _fallback_tabs(), (
        "Could not load the built-in keyboard; using the numeric keypad."
    )


def load_keyboard_tabs(path: Path | None = None) -> list[dict[str, Any]]:
    """The tab descriptors from `load_keyboard_layout`, discarding its message."""
    return load_keyboard_layout(path)[0]


def _keyboard_filename(name: str) -> str:
    """Validate a user-supplied layout name, adding ``.yaml`` when omitted."""
    if not isinstance(name, str):
        raise ValueError("Name is required")
    name = name.strip()
    if not name:
        raise ValueError("Name is required")
    if name.startswith(".") or name in (".", ".."):
        raise ValueError("Name cannot start with a dot")
    if Path(name).name != name or any(ch in '<>:"/\\|?*' or ord(ch) < 32
                                      for ch in name):
        raise ValueError("Name cannot contain a path or reserved characters")
    suffix = Path(name).suffix.lower()
    if not suffix:
        name += ".yaml"
    elif suffix not in KEYBOARD_SUFFIXES:
        raise ValueError("Use a .yaml or .yml filename")
    return name


def new_keyboard_file(
    directory: Path,
    source: Path | None = None,
    name: str | None = None,
) -> Path:
    """Copy a layout into ``directory``.

    The source is validated before anything is written, so a damaged packaged
    default cannot become a new broken custom file. With ``name`` the caller
    chooses the filename (``.yaml`` is appended when no suffix is given) and a
    collision is an error; without it the first free ``keyboard-N.yaml`` is
    used. The exclusive create means an existing file is never overwritten.
    """
    source = Path(source) if source is not None else KEYBOARD_CONFIG_PATH
    if not _tabs_from_path(source):
        raise ValueError(f"{source} is not a usable keyboard layout")

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    explicit = name is not None
    if explicit:
        name = _keyboard_filename(name)
        candidates = (directory / name,)
    else:
        candidates = (
            directory / ("keyboard-1.yaml" if index == 1
                         else f"keyboard-{index}.yaml")
            for index in count(1)
        )

    for target in candidates:
        try:
            with target.open("xb") as f:
                f.write(data)
        except FileExistsError:
            if explicit:
                raise FileExistsError(f"{target.name} already exists") from None
            continue
        except OSError:
            try:
                target.unlink()
            except OSError:
                pass
            raise
        return target

    raise RuntimeError("could not allocate a keyboard filename")


def label_glyphs(path: Path | None = None) -> str:
    """Every character the keys can *show*, as a string to test fonts against.

    Derived from the layout itself rather than a hand-kept list, so adding a key
    with a new glyph automatically makes that glyph part of "the keyboard font
    must render this". Punctuation and ASCII are included and will pass
    everywhere; the interesting entries are the mathematical ones (∞ √ ∛ ≤ ≥),
    which are exactly what a general-purpose face can be missing. LaTeX keys
    keep their labels in this set: the label is the fallback if rendering fails,
    so the keyboard font still needs it.
    """
    characters = {
        char
        for tab in load_keyboard_tabs(path)
        for key in tab["keys"] + tab.get("shiftKeys", [])
        for char in key["label"]
    }
    return "".join(sorted(characters))
