# coding: utf-8
"""Keyboard layout helpers for the QML app.

Loads the keyboard config YAML and flattens each tab's grid into the keys QML
places with GridLayout attached properties. A key carries two strings: the
``label`` it shows and the ``insert`` text it types — the same string for most
keys, but not for the ones whose glyph differs from the function they insert
(``√`` shows, ``sqrt(`` types).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

KEYBOARD_CONFIG_PATH = Path(__file__).resolve().parent / "keyboard_config.yaml"

#: Minimal numeric keypad used when the YAML config cannot be loaded.
FALLBACK_GRID: List[List[str]] = [
    ["7", "8", "9", "/"],
    ["4", "5", "6", "*"],
    ["1", "2", "3", "-"],
    ["0", ".", "=", "+"],
]


def _flatten_cell(cell: Any) -> Optional[Dict[str, str]]:
    """One grid cell as ``{'label', 'insert'}``, or None when the cell is empty.

    A cell is either a plain string — the common case, where the key shows the
    text it types — or a mapping with ``label``/``insert`` for a key whose glyph
    differs. A mapping may give only one of the two, which then supplies both.
    """
    if isinstance(cell, str):
        return {"label": cell, "insert": cell} if cell else None
    if isinstance(cell, dict):
        insert = str(cell.get("insert") or "")
        label = str(cell.get("label") or "")
        if not insert and not label:
            return None
        return {"label": label or insert, "insert": insert or label}
    return None


def _flatten_grid(grid: List[List[Any]]) -> Dict[str, Any]:
    """Flatten a 2D grid of key cells into columns/keys."""
    columns = max((len(row) for row in grid), default=1)
    keys: List[Dict[str, Any]] = []
    for row_idx, row in enumerate(grid):
        for col_idx, cell in enumerate(row):
            flattened = _flatten_cell(cell)
            if flattened is not None:
                keys.append({**flattened, "row": row_idx, "col": col_idx})
    return {"columns": columns, "keys": keys}


def load_keyboard_tabs() -> List[Dict[str, Any]]:
    """Load the keyboard layout, flattening each tab's grid.

    Each tab becomes ``{"title", "columns", "keys": [{label, insert, row, col}]}``.
    Falls back to a minimal numeric keypad when the file is missing, empty, or
    not a mapping — a hand-edited layout must never break startup.

    Returns:
        A list of tab descriptors usable as a QML model.
    """
    try:
        with open(KEYBOARD_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        config = None

    # A list/scalar at the root (or a missing file) has no tabs to iterate.
    if not isinstance(config, dict) or not config:
        return [{"key": "basic", "title": "Basic", **_flatten_grid(FALLBACK_GRID)}]

    tabs: List[Dict[str, Any]] = []
    for route_key, tab in config.items():
        if not isinstance(tab, dict):
            continue  # a malformed tab contributes no keys
        grid = tab.get("grid")
        tabs.append(
            {
                "key": route_key,
                "title": tab.get("title", route_key),
                **_flatten_grid(grid if isinstance(grid, list) else []),
            }
        )
    return tabs or [{"key": "basic", "title": "Basic", **_flatten_grid(FALLBACK_GRID)}]


def label_glyphs() -> str:
    """Every character the keys can *show*, as a string to test fonts against.

    Derived from the layout itself rather than a hand-kept list, so adding a key
    with a new glyph automatically makes that glyph part of "the keyboard font
    must render this". Punctuation and ASCII are included and will pass
    everywhere; the interesting entries are the mathematical ones (∞ √ ∛ ≤ ≥),
    which are exactly what a general-purpose face can be missing.
    """
    characters = {
        char
        for tab in load_keyboard_tabs()
        for key in tab["keys"]
        for char in key["label"]
    }
    return "".join(sorted(characters))
