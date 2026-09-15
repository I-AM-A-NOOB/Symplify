# coding: utf-8
"""Boots RinUI so its own config file never appears next to the app.

RinUI persists theme/backdrop/accent by itself, and it does so **at import time**:
``RinUI/core/config.py`` computes ``BASE_DIR = Path.cwd()`` and, when
``<BASE_DIR>/RinUI/config/rin_ui.json`` is missing, creates it right there. There
is no supported switch to redirect or disable that (verified against 0.4.4.1).

This module takes the location back, in four steps — see :func:`prepare`:

1. ``chdir`` into a throwaway temporary directory for the duration of
   ``import RinUI``, so the file it writes lands there and is deleted with that
   directory right afterwards — nothing RinUI-shaped is left anywhere;
2. inject our appearance settings into ``RinConfig`` and neutralise
   ``RinConfig.save_config`` — RinUI's only write funnel (``load_config``,
   ``upload_config`` and ``__setitem__`` all call it) — so nothing RinUI does can
   persist again;
3. on the first run of this scheme, fold a legacy ``<app>/RinUI/config`` into our
   settings file and remove that directory;
4. hand the settings store and RinUI's window class to the composition root.

**The settings file is the single source of truth.** Never re-enable RinUI's own
persistence, and never import ``RinUI`` before :func:`prepare` has run.
"""

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .settings import CONFIG_FILENAME, DEFAULTS, SettingsStore, resolve_config_dir

#: RinUI's config file name inside its own directory.
_RINUI_FILENAME = "rin_ui.json"


@dataclass(frozen=True)
class Runtime:
    """What the bootstrap hands back to the composition root.

    Everything RinUI-shaped is wrapped here so ``main.py`` never has to import
    ``RinUI`` at module level (which would build the config directory in the
    current working directory before :func:`prepare` could take it over).
    """

    settings: SettingsStore
    window_class: type
    rinui_version: str


def prepare(root: Path) -> Runtime:
    """Load the settings and take over RinUI's configuration.

    Call this before creating a ``QApplication`` and before using anything from
    ``RinUI`` (it performs the import itself).

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

    # The import writes RinUI's own config file when it is missing, at the
    # cwd-relative path <cwd>/RinUI/config/rin_ui.json. Do it from a throwaway
    # directory: nothing RinUI-shaped is left anywhere the user can see (our
    # config directory holds only config.yaml), and there is no placeholder file
    # to keep in sync. The directory is removed again right after the import —
    # nothing reads it afterwards, and writes were just disabled.
    cwd = Path.cwd()
    scratch = Path(tempfile.mkdtemp(prefix="symplify-boot-"))
    os.chdir(scratch)
    try:
        import RinUI
        from RinUI import RinUIWindow
        from RinUI.core.config import DEFAULT_CONFIG, RinConfig
    finally:
        os.chdir(cwd)
        shutil.rmtree(scratch, ignore_errors=True)

    if first_run:
        # A fresh install takes RinUI's own platform detection (mica on Win11,
        # acrylic on Win10, none elsewhere) instead of our hardcoded default,
        # which would be wrong on older Windows. The migration runs *after* it,
        # so a legacy configuration still wins over the platform default.
        store.set("appearance.backdrop", DEFAULT_CONFIG["backdrop_effect"])
        _migrate(store, Path(root))

    RinConfig.config = _rinui_config(store, DEFAULT_CONFIG)
    RinConfig.save_config = lambda: None  # RinUI must never write a file again
    return Runtime(store, RinUIWindow, RinUI.__version__)


def _rinui_config(store: SettingsStore, defaults: Dict[str, Any]) -> Dict[str, Any]:
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
