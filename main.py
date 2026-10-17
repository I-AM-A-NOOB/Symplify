# coding: utf-8
"""Symplify entry point (composition root).

Builds the viewmodels, registers them as flat QML context properties,
and lets RinUI load the Fluent-styled QML window.
"""

import sys
from pathlib import Path

from PySide6.QtCore import qVersion
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from qmlmathplot import register_qml_types

# The bootstrap owns the RinUI import (and takes RinUI's own config directory
# over, see python/rinui_bootstrap.py). Never import RinUI above this line.
from python import window_icon
from python.model.plotting import plot_variables
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

    # QMLMathPlot's types (PlotView and the model objects behind it) are
    # registered per process, and the QML loader needs them before it parses a
    # page — the window's engine is created by the runtime below. Idempotent.
    register_qml_types()

    app = QApplication(sys.argv)

    # Every surface that asks the application for its icon — the window's title
    # bar, the taskbar button, alt-tab — would otherwise show Qt's default.
    #
    # The SVG comes first because it is the only source and it scales: Qt's
    # `qsvgicon` engine (shipped in the build, see scripts/build_windows.py)
    # registers it as scalable, so every request is drawn at the size asked for —
    # measured: it answers 16 through 512 px, `availableSizes()` reports none
    # because there is no bound, and the 128 px alt-tab tile is not an upscaled
    # bitmap. The .ico is added as well and answers only if the SVG engine cannot
    # load (a pruned plugin, a missing file), so a broken vector still leaves a
    # real icon instead of Qt's default placeholder; it is also the same file
    # Nuitka embeds into the exe.
    icon = QIcon()
    icon.addFile(str(ROOT / "icon" / "Symplify.svg"))
    icon.addFile(str(ROOT / "icon" / "Symplify.ico"))
    app.setWindowIcon(icon)

    # Qt Quick scrolls a `Flickable` by `wheelScrollLines * 24` pixels per wheel
    # notch — `qquickflickable.cpp`: `wheelScroll = -styleHints()->wheelScrollLines() * 24`
    # — so the stock 3 moves 72px a notch, which reads as sluggish next to Windows'
    # own apps. That hint is the only *global* lever there is: one value for every
    # scrolling surface, RinUI's included. 5 → 120px per notch.
    app.styleHints().setWheelScrollLines(5)

    # Create the RinUI window shell first (without loading QML) so that the
    # shared engine's root context can receive the viewmodels before the
    # QML tree is instantiated.
    window = runtime.window_class()

    vm = MainViewModel(runtime.settings, window.theme_manager,
                       initial_variables=plot_variables())
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

    # Qt's warnings and any uncaught exception used to go only to a console a
    # windowed build does not have (see python/log_capture.py). Installed before
    # the QML loads, so engine-level complaints land in the Log page too.
    vm.install_log_capture()

    window.load(ROOT / "qml" / "MainWindow.qml")

    # And once more now that the QML has built the window. This is not
    # belt-and-braces: without it the taskbar button is a blank square.
    # (Its class icon is set too, because that is what the shell falls back to
    # while this window is still being built — see `python/window_icon.py`.)
    #
    # `app.setWindowIcon` above gives every window created afterwards this icon,
    # and Qt does put it on the window — measured on the live HWND, `ICON_SMALL`
    # and `ICON_BIG` both hold our artwork. But the shell snapshots a taskbar
    # button's icon when the button appears, and by then RinUI has changed the
    # window's flags (`FluentWindowBase.Component.onCompleted` clears
    # `FramelessWindowHint`), which makes Qt recreate the native window
    # underneath the shell's feet — so what the button took was the *class* icon
    # Qt registers, `IDI_APPLICATION`, an empty square. Alt+Tab never showed the
    # problem because it reads the window's icon live; the button re-reads only
    # when the icon changes, which is exactly what this does.
    window.root_window.setIcon(icon)
    window_icon.apply_to_window_class(window.root_window,
                                      ROOT / "icon" / "Symplify.ico")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
