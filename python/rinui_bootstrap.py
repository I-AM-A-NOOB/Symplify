"""Boots RinUI with Symplify's settings as its only configuration.

RinUI keeps its own settings (theme, backdrop, accent) and, up to 0.4.x, wrote
them **at import time** to ``<cwd>/RinUI/config/rin_ui.json``. 0.5 resolves the
location with ``QStandardPaths`` instead and only reads it when the first
``RinUIWindow`` is constructed, so importing the library no longer touches the
working directory — the temporary-directory dance this module used to perform is
gone.

What remains is the takeover of the *values*: our settings file is the single
source of truth, and RinUI must never persist its own. ``prepare`` wraps RinUI's
``init_config`` so our mapping lands after its load and before ``ThemeManager``
reads it, disables ``RinConfig.save_config``, installs the Windows window fixes,
and hands the store and RinUI's window class to the composition root. Call it
before creating a ``QApplication`` (RinUI's window class is created later, once
the app exists).
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import window_drag
from .settings import CONFIG_FILENAME, DEFAULTS, SettingsStore, resolve_config_dir

#: RinUI's config file name inside its own directory.
_RINUI_FILENAME = "rin_ui.json"


@dataclass(frozen=True)
class Runtime:
    """What the bootstrap hands back to the composition root.

    Everything RinUI-shaped is wrapped here so ``main.py`` never imports
    ``RinUI`` itself; :func:`prepare` is the one place that configures it.
    """

    settings: SettingsStore
    window_class: type
    rinui_version: str


def prepare(root: Path) -> Runtime:
    """Load the settings and take over RinUI's configuration.

    Call this before creating a ``QApplication`` and before building RinUI's
    window class (the window is constructed later, once the app exists).

    Args:
        root: The app root — the exe directory when frozen, the repo root in dev.

    Returns:
        A :class:`Runtime` with the settings store, RinUI's window class and its
        version string.
    """
    directory, is_portable = resolve_config_dir(root)
    first_run = not (directory / CONFIG_FILENAME).is_file()
    store = SettingsStore(directory / CONFIG_FILENAME, is_portable)
    store.load()

    import RinUI
    from RinUI import RinUIWindow
    from RinUI.core import launcher as rinui_launcher
    from RinUI.core.config import DEFAULT_CONFIG, RinConfig

    # RinUI 0.5 loads its own config into `RinConfig` inside `RinUIWindow.__init__`
    # (`init_config()`), and `ThemeManager` reads it immediately afterwards. Our
    # mapping therefore has to be applied *between* those two calls: assigning
    # `RinConfig.config` here would be overwritten. Replace the name the launcher
    # imported with a wrapper instead — the same trick `window_drag` uses for
    # `WinEventManager`.
    original_init_config = rinui_launcher.init_config

    def init_config_with_our_settings():
        config = original_init_config()
        config.config = _rinui_config(store, DEFAULT_CONFIG)
        return config

    setattr(rinui_launcher, "init_config", init_config_with_our_settings)

    #: RinUI's only write funnel (`load_config`, `upload_config` and
    #: `__setitem__` all call it), and `load_config` saves the defaults when the
    #: file is missing — so this must be in place before `init_config()` runs.
    RinConfig.save_config = lambda: None

    # RinUI's window-event manager exists only on Windows: its module imports
    # pywin32 at the top, which is why RinUI's own __init__ imports it under the
    # same condition. The drag (and fullscreen hit-test) fixes go in there too.
    if window_drag.WINDOWS:
        from RinUI.core.window import WinEventManager

        window_drag.install(WinEventManager)

    if first_run:
        # A fresh install takes RinUI's own platform detection (mica on Win11,
        # acrylic on Win10, none elsewhere) instead of our hardcoded default,
        # which would be wrong on older Windows. The migration runs *after* it,
        # so a legacy configuration still wins over the platform default.
        store.set("appearance.backdrop", DEFAULT_CONFIG["backdrop_effect"])
        _migrate(store, Path(root))

    return Runtime(store, RinUIWindow, RinUI.__version__)


def _rinui_config(store: SettingsStore, defaults: dict[str, Any]) -> dict[str, Any]:
    """RinUI's config mapping, carrying our appearance settings.

    ``win10_feat`` has to survive: it holds the backdrop alpha values RinUI needs
    on Windows 10.

    The accent is injected as a *colour*, because RinUI's config has no notion of
    where it came from: a ``custom`` mode injects the stored colour, every other
    mode RinUI's own (so does ``system`` — reading the palette needs a running
    application, which does not exist until after :func:`prepare`, and the QML
    side replaces it before the first frame is painted).
    """
    config = json.loads(json.dumps(defaults))  # deep copy of the library defaults
    config["theme"] = {"current_theme": store.get("appearance.theme")}
    config["backdrop_effect"] = store.get("appearance.backdrop")
    config["theme_color"] = (
        store.get("appearance.accent")
        if store.get("appearance.accent_mode") == "custom"
        else DEFAULTS["appearance"]["accent"]
    )
    return config


def _migrate(store: SettingsStore, root: Path) -> None:
    """Fold a legacy ``<root>/RinUI/config/rin_ui.json`` into our settings.

    Only called on the first run of the new scheme, so it can never clobber
    settings the user has since changed. The directory is removed afterwards:
    only its own config file is deleted, and the empty folders are dropped with
    ``rmdir`` so anything else the user put there survives.
    """
    legacy = root / "RinUI" / "config" / _RINUI_FILENAME
    if legacy.is_file():
        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        theme = (data.get("theme") or {}).get("current_theme")
        if theme in ("Auto", "Light", "Dark"):
            store.set("appearance.theme", theme)
        if isinstance(data.get("backdrop_effect"), str):
            store.set("appearance.backdrop", data["backdrop_effect"])
        if isinstance(data.get("theme_color"), str):
            store.set("appearance.accent", data["theme_color"])
            # The legacy colour *was* the running accent, so it has to arrive as
            # a custom choice — the default mode would ignore it. Unless it *is*
            # RinUI's default: nothing was ever picked then, so staying on
            # `default` keeps following the library's own accent.
            if data["theme_color"].lower() != DEFAULTS["appearance"]["accent"].lower():
                store.set("appearance.accent_mode", "custom")

    legacy.unlink(missing_ok=True)
    for folder in (root / "RinUI" / "config", root / "RinUI"):
        try:
            folder.rmdir()
        except OSError:
            pass          # not empty (or already gone): leave whatever is in there
