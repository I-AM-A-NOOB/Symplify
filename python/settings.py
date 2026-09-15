# coding: utf-8
"""Application settings: where they live and how they are stored.

Pure Python (no Qt) so the whole store is testable headless.

**Location**, in priority order:

1. *Portable*: if a ``data`` directory exists next to the app (the exe's
   directory when frozen, the repository root otherwise), settings live in
   ``<root>/data/config.yaml`` — ship that folder and the app is
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

from .fonts import DEFAULT_CODE_FAMILY, DEFAULT_KEYBOARD_FAMILY

#: Directory (next to the app) whose presence switches on portable mode.
PORTABLE_DIRNAME = "data"

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
        "accent": "#605ed2",      # the CUSTOM accent colour, #rrggbb (accent_mode == custom)
        "accent_mode": "default", # default (RinUI's own colour) | system (QPalette) | custom
        # Finetune the accent per colour scheme with our own WinUI-style steps,
        # for every mode. Off uses each colour exactly as it is.
        "accent_shading": True,
        # Use the OS's own tuned accent per scheme where it has one (Windows)
        # instead of the built-in blend. Only meaningful with the system accent
        # and shading on; see SettingsViewModel.accentOsShadingAvailable.
        "accent_os_shading": True,
    },
    "fonts": {
        # A comma-separated PREFERENCE list, resolved to the first family the
        # system has (QML cannot express a fallback list — see python/fonts.py).
        "code_family": DEFAULT_CODE_FAMILY,
        "code_size": 14,          # code text: inputs, outputs, log, table cells
        "keyboard_family": DEFAULT_KEYBOARD_FAMILY,
        "keyboard_size": 16,
        "latex_font": "",         # "" = ziamath's bundled STIX Two Math
        "latex_size": 24,         # ziamath's own default font size, in points
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
    "appearance.accent_mode": ("default", "system", "custom"),
}

#: Keys clamped into a numeric range.
_CLAMPS = {
    "fonts.code_size": (6, 72),
    "fonts.keyboard_size": (6, 72),
    "fonts.latex_size": (8, 96),
    "window.width": (860, 20000),
    "window.height": (560, 20000),
}

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

#: Every leaf key that must be validated on load and on write.
_KNOWN_KEYS = (
    "appearance.theme",
    "appearance.backdrop",
    "appearance.accent",
    "appearance.accent_mode",
    "appearance.accent_shading",
    "appearance.accent_os_shading",
    "fonts.code_family",
    "fonts.code_size",
    "fonts.keyboard_family",
    "fonts.keyboard_size",
    "fonts.latex_font",
    "fonts.latex_size",
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
        default = values.get(key)
        if isinstance(value, dict) and isinstance(default, dict):
            # A section: overlay the loaded keys onto the defaults.
            values[key].update(value)
        elif not isinstance(default, dict):
            # A leaf key (or an unknown top-level key): take the loaded value,
            # validation/clamping runs afterwards.
            values[key] = value
        # A scalar loaded where the default is a section is deliberately
        # ignored: it cannot be merged, and storing it would replace the whole
        # section and break downstream writes and the latex-size migration.
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
        self._infer_accent_mode(loaded)
        self._migrate_latex_size(loaded)
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

    def _infer_accent_mode(self, loaded: Any) -> None:
        """Treat an accent colour written before accent modes existed as custom.

        Such a file has no ``accent_mode`` key, and the colour it holds *was*
        the accent the app applied — falling back to the ``default`` mode would
        silently drop the user's choice.
        """
        appearance = loaded.get("appearance") if isinstance(loaded, dict) else None
        if (isinstance(appearance, dict)
                and "accent" in appearance
                and "accent_mode" not in appearance):
            self.values["appearance"]["accent_mode"] = "custom"

    def _migrate_latex_size(self, loaded: Any) -> None:
        """Move a pre-``fonts`` ``rendering.latex_size`` into the fonts section.

        The key only moved; the value is still the result font size, so a file
        written before the Typography section existed keeps its setting. An
        already-present ``fonts.latex_size`` wins (the user has been through the
        new page and the old key is stale).
        """
        if not isinstance(loaded, dict):
            return
        rendering = loaded.get("rendering")
        fonts = loaded.get("fonts")
        if not isinstance(rendering, dict) or "latex_size" not in rendering:
            return
        if isinstance(fonts, dict) and "latex_size" in fonts:
            return
        self.values["fonts"]["latex_size"] = rendering["latex_size"]

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
        if key in ("fonts.code_family", "fonts.keyboard_family"):
            # A preference LIST: keep it verbatim so nothing the user typed is
            # silently dropped; only a non-string or an empty list falls back.
            text = value.strip() if isinstance(value, str) else ""
            return text if text else default
        if key == "fonts.latex_font":
            # A family name from the dropdown, or "" for ziamath's own font.
            return value.strip() if isinstance(value, str) else default
        if key in ("window.x", "window.y"):
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        if key in ("window.maximized", "window.remember",
                   "appearance.accent_shading",
                   "appearance.accent_os_shading"):
            return bool(value)
        return value
