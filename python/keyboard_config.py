# coding: utf-8
"""Keyboard layout helpers for the QML app.

Loads the keyboard config YAML and flattens each tab's grid so QML can
place buttons with GridLayout attached properties. If the YAML file is
missing or unreadable, a minimal numeric keypad is used as a fallback.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml

KEYBOARD_CONFIG_PATH = Path(__file__).resolve().parent / "keyboard_config.yaml"

#: Minimal numeric keypad used when the YAML config cannot be loaded.
FALLBACK_GRID: List[List[str]] = [
    ["7", "8", "9", "/"],
    ["4", "5", "6", "*"],
    ["1", "2", "3", "-"],
    ["0", ".", "=", "+"],
]


def _flatten_grid(grid: List[List[str]]) -> Dict[str, Any]:
    """Flatten a 2D grid of button labels into columns/keys."""
    columns = max((len(row) for row in grid), default=1)
    keys: List[Dict[str, Any]] = []
    for row_idx, row in enumerate(grid):
        for col_idx, label in enumerate(row):
            if label:
                keys.append({"text": label, "row": row_idx, "col": col_idx})
    return {"columns": columns, "keys": keys}


def load_keyboard_tabs() -> List[Dict[str, Any]]:
    """Load the keyboard layout, flattening each tab's grid.

    Each tab becomes ``{"title", "columns", "keys": [{text, row, col}]}``.
    Falls back to a minimal numeric keypad if the config file is missing.

    Returns:
        A list of tab descriptors usable as a QML model.
    """
    try:
        with open(KEYBOARD_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        config = {}

    if not config:
        return [{"key": "basic", "title": "Basic", **_flatten_grid(FALLBACK_GRID)}]

    tabs: List[Dict[str, Any]] = []
    for route_key, tab in config.items():
        grid = tab.get("grid") or []
        tabs.append(
            {
                "key": route_key,
                "title": tab.get("title", route_key),
                **_flatten_grid(grid),
            }
        )
    return tabs
