# coding: utf-8
"""Symplify entry point (composition root).

Builds the viewmodels, registers them as flat QML context properties,
and lets RinUI load the Fluent-styled QML window.
"""

import sys
from pathlib import Path

from PySide6.QtCore import qVersion
from PySide6.QtWidgets import QApplication

# The bootstrap owns the RinUI import (and takes RinUI's own config directory
# over, see python/rinui_bootstrap.py). Never import RinUI above this line.
from python.rinui_bootstrap import prepare
from python.keyboard_config import load_keyboard_tabs
from python.viewmodel.main_viewmodel import MainViewModel
from python.version import __version__

# Under Nuitka the entry module is the compiled binary, so resolve the
# project root relative to the executable instead of __file__.
if "__compiled__" in globals():
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent


def main() -> int:
    """Create the app, wire the viewmodels, and start the event loop."""
    # RinUI prints emoji to stdout; force UTF-8 so GBK consoles don't crash.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    runtime = prepare(ROOT)

    app = QApplication(sys.argv)

    # Create the RinUI window shell first (without loading QML) so that the
    # shared engine's root context can receive the viewmodels before the
    # QML tree is instantiated.
    window = runtime.window_class()

    vm = MainViewModel(runtime.settings, window.theme_manager)
    context = window.engine.rootContext()
    context.setContextProperty("vm", vm)
    context.setContextProperty("appVersion", __version__)
    # RinUI's own __version__ (not importlib.metadata: a frozen build has no
    # .dist-info, so metadata lookups would raise).
    context.setContextProperty("rinuiVersion", runtime.rinui_version)
    # Qt's QML global qtRuntimeVersionString does not exist under PySide6, so
    # the About page would silently lose the Qt version; pass qVersion() down.
    context.setContextProperty("qtVersion", qVersion())
    context.setContextProperty("calcVM", vm.calculator)
    context.setContextProperty("varsVM", vm.variables)
    context.setContextProperty("variablesModel", vm.variables.model)
    context.setContextProperty("variablesFilter", vm.variablesFilter)
    context.setContextProperty("historyVM", vm.history)
    context.setContextProperty("historyFilter", vm.historyFilter)
    context.setContextProperty("logVM", vm.log)
    context.setContextProperty("settingsVM", vm.settings)
    context.setContextProperty("keyboardTabs", load_keyboard_tabs())

    window.load(ROOT / "qml" / "MainWindow.qml")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
