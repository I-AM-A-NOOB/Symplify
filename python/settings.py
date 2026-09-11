# coding: utf-8
"""Application settings: where they live and how they are stored.

Pure Python (no Qt) so the whole store is testable headless.

**Location**, in priority order:

1. *Portable*: if a ``Data`` directory exists next to the app (the exe's
   directory when frozen, the repository root otherwise), settings live in
   ``<root>/Data/config.yaml`` — ship that folder and the app is
   self-contained.
2. Otherwise the platform's user configuration directory:

   =========  ===========================================================
   Windows    ``%APPDATA%\\Symplify\\config.yaml`` (falls back to
              ``%LOCALAPPDATA%``, then the home directory)
   Linux      ``$XDG_CONFIG_HOME/symplify/config.yaml`` (falls back to
              ``~/.config/symplify/config.yaml``)
   macOS      ``~/Library/Application Support/Symplify/config.yaml``
   =========  ===========================================================

**Format** is YAML: PyYAML is already a dependency (the keyboard layout uses
it), it tolerates comments in a hand-edited file, and one library both reads and
writes it. Writes are **atomic** — a temporary file in the same directory plus
``os.replace`` — so a crash or a full disk cannot leave a half-written config.

A broken or hand-edited file never breaks startup: unknown keys are preserved,
known keys are validated and clamped, and anything unreadable falls back to the
defaults (with ``warning`` set for the UI to show).
"""

import copy
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

#: Directory (next to the app) whose presence switches on portable mode.
PORTABLE_DIRNAME = "Data"

#: Settings file name inside the resolved configuration directory.
CONFIG_FILENAME = "config.yaml"

#: Folder name used under the platform's config directory.
APP_DIRNAME = "Symplify"

#: Every setting the app understands, with its default.
DEFAULTS: Dict[str, Any] = {
    "version": 1,
    "appearance": {
        "theme": "Auto",          # Auto | Light | Dark
        "backdrop": "mica",       # mica | acrylic | tabbed | none (Windows only)
        "accent": "#605ed2",      # accent colour, #rrggbb
    },
    "rendering": {
        "latex_size": 24,         # result LaTeX font size, in points
    },
    "window": {
        "remember": True,         # restore size/position on the next launch
        "width": 1180,
        "height": 760,
        "x": None,                # None = let the window manager decide
        "y": None,
        "maximized": False,
    },
}

#: Keys restricted to a fixed set of values.
_CHOICES = {
    "appearance.theme": ("Auto", "Light", "Dark"),
    "appearance.backdrop": ("mica", "acrylic", "tabbed", "none"),
}

#: Keys clamped into a numeric range.
_CLAMPS = {
    "rendering.latex_size": (8, 96),
    "window.width": (860, 20000),
    "window.height": (560, 20000),
}

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

#: Every leaf key that must be validated on load and on write.
_KNOWN_KEYS = (
    "appearance.theme",
    "appearance.backdrop",
    "appearance.accent",
    "rendering.latex_size",
    "window.remember",
    "window.width",
    "window.height",
    "window.x",
    "window.y",
    "window.maximized",
)


def _platform(system: Optional[str] = None) -> str:
    """Which platform's convention to follow (overridable for tests)."""
    if system:
        return system
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def resolve_config_dir(
    root: Path,
    env: Optional[Dict[str, str]] = None,
    system: Optional[str] = None,
) -> Tuple[Path, bool]:
    """Resolve the configuration directory for this launch.

    Args:
        root: The app root (exe directory when frozen, repo root in dev).
        env: Environment mapping; defaults to ``os.environ`` (tests inject one).
        system: ``"windows"``/``"macos"``/``"linux"``; defaults to this platform.

    Returns:
        ``(directory, is_portable)``. The directory is not created here.
    """
    env = dict(os.environ if env is None else env)
    if (Path(root) / PORTABLE_DIRNAME).is_dir():
        return Path(root) / PORTABLE_DIRNAME, True

    home = Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    if _platform(system) == "windows":
        base = env.get("APPDATA") or env.get("LOCALAPPDATA")
        return (Path(base) / APP_DIRNAME if base else home / APP_DIRNAME), False
    if _platform(system) == "macos":
        return home / "Library" / "Application Support" / APP_DIRNAME, False
    xdg = env.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else home / ".config"
    return base / APP_DIRNAME.lower(), False


def _merge_defaults(loaded: Any) -> Dict[str, Any]:
    """Overlay a loaded mapping onto the defaults (unknown keys survive)."""
    values = copy.deepcopy(DEFAULTS)
    if not isinstance(loaded, dict):
        return values
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(values.get(key), dict):
            values[key].update(value)
        else:
            values[key] = value
    return values


class SettingsStore:
    """Loads, validates and persists the application settings."""

    def __init__(self, path: Path, is_portable: bool = False):
        """Initialize the store for ``path`` (not read yet — call :meth:`load`)."""
        self.path = Path(path)
        self.is_portable = is_portable
        self.values: Dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.warning = ""

    @classmethod
    def open(
        cls,
        root: Path,
        env: Optional[Dict[str, str]] = None,
        system: Optional[str] = None,
    ) -> "SettingsStore":
        """Resolve the config location for ``root``, then load it."""
        directory, is_portable = resolve_config_dir(root, env, system)
        store = cls(directory / CONFIG_FILENAME, is_portable)
        store.load()
        return store

    def load(self) -> None:
        """Read the file (if any) and normalize every known key."""
        self.warning = ""
        loaded: Any = {}
        try:
            if self.path.is_file():
                loaded = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            self.warning = f"config unreadable, using defaults: {exc}"
        self.values = _merge_defaults(loaded)
        for key in _KNOWN_KEYS:
            self._write_key(key, self._validate_known(key, self.get(key)))

    def get(self, key: str, default: Any = None) -> Any:
        """Read a dotted key (``appearance.theme``), falling back to its default."""
        node: Any = self.values
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                value = self._default_for(key)
                return default if value is None else value
            node = node[part]
        return node

    def set(self, key: str, value: Any) -> Any:
        """Validate ``value``, store it and persist; returns what was stored."""
        self.update({key: value})
        return self.get(key)

    def update(self, values: Dict[str, Any]) -> None:
        """Set several dotted keys and persist once (window geometry, resets)."""
        for key, value in values.items():
            self._write_key(key, self._validate_known(key, value))
        self.save()

    def reset(self) -> None:
        """Restore every default and persist."""
        self.values = copy.deepcopy(DEFAULTS)
        self.save()

    def save(self) -> bool:
        """Write the file atomically. Returns False (and warns) on failure."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(
                yaml.safe_dump(self.values, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        except OSError as exc:
            self.warning = f"settings not saved: {exc}"
            return False
        self.warning = ""
        return True

    # --- internals --------------------------------------------------------

    def _default_for(self, key: str) -> Any:
        node: Any = DEFAULTS
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return copy.deepcopy(node)

    def _write_key(self, key: str, value: Any) -> None:
        parts = key.split(".")
        node = self.values
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def _validate_known(self, key: str, value: Any) -> Any:
        """Clamp/repair a value for a known key (unknown keys pass through)."""
        default = self._default_for(key)
        if key in _CHOICES:
            return value if value in _CHOICES[key] else default
        if key in _CLAMPS:
            low, high = _CLAMPS[key]
            try:
                number = int(value)
            except (TypeError, ValueError):
                return default
            return max(low, min(high, number))
        if key == "appearance.accent":
            return value if isinstance(value, str) and _HEX_COLOR.match(value) else default
        if key in ("window.x", "window.y"):
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        if key == "window.maximized" or key == "window.remember":
            return bool(value)
        return value
