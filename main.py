"""Symplify entry point (composition root).

Builds the viewmodels, registers them as flat QML context properties,
and lets RinUI load the Fluent-styled QML window.
"""

import multiprocessing
import sys
from pathlib import Path

# The UI, SymPy and qmlmathplot imports deliberately live inside `main()`.
# `multiprocessing`'s spawn re-imports this module in every worker; top-level
# imports made the "zero Qt" calculation/render workers pay for PySide6 and
# qmlmathplot before their own modules even loaded. Importing `main` must stay
# light so a worker starts with only what its target needs.

# Under Nuitka the entry module is the compiled binary, so resolve the
# project root relative to the executable instead of __file__.
if "__compiled__" in globals():
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent


#: Seconds a single calculation may run before the worker is terminated. The
#: value is a UI deadline, not a model limit: the inline backend has none, and a
#: timeout is reported as a failure rather than a partial answer.
CALCULATION_TIMEOUT_SECONDS = 10.0


def main() -> int:
    """Create the app, wire the viewmodels, and start the event loop."""
    # Nuitka standalone builds spawn the calculation worker by re-running this
    # executable with multiprocessing's flag. freeze_support() is what routes
    # that back into the worker; it is a no-op in a normal interpreter, and it
    # must stay ahead of the UI imports below.
    multiprocessing.freeze_support()

    from PySide6.QtCore import qVersion
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from qmlmathplot import register_qml_types

    # The bootstrap owns RinUI's configuration (see python/rinui_bootstrap.py),
    # and this composition root gets the window class from it rather than
    # importing RinUI itself.
    from python import window_drag, window_icon
    from python.rinui_bootstrap import prepare
    from python.store_client import StoreClient
    from python.version import __version__
    from python.viewmodel.calculation_backend import ProcessBackend
    from python.viewmodel.main_viewmodel import MainViewModel

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

    # The variable Store is a separate process with no SymPy; it owns the
    # authoritative strings and the revision every calculation is computed
    # against. A fresh Store is **empty**: x and y are ordinary free symbols the
    # parser creates on demand, and the plot reads them from the result, so
    # pre-seeding them only put two rows in the table that the user never added.
    # Assigning them warns like any plotting name. The snapshot sits beside the
    # settings file (portable or OS config), and a different SymPy version sets
    # it aside rather than restoring potentially incompatible srepr.
    store = StoreClient(runtime.settings.path.with_name("variables.json"))
    store.bootstrap()
    app.aboutToQuit.connect(store.close)

    vm = MainViewModel(
        runtime.settings,
        window.theme_manager,
        store_client=store,
        calculation_backend=ProcessBackend(CALCULATION_TIMEOUT_SECONDS),
        variables_backend=ProcessBackend(CALCULATION_TIMEOUT_SECONDS),
        translation_dir=ROOT / "i18n",
        icon_dir=ROOT / "icon",
        history_path=runtime.settings.path.with_name("history.json"),
    )
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
    context.setContextProperty("historyWindow", vm.historyWindow)
    context.setContextProperty("logVM", vm.log)
    context.setContextProperty("settingsVM", vm.settings)
    # QML does not retranslate existing bindings on its own when a translator
    # is installed after the tree exists. The engine has the explicit hook.
    vm.settings.languageChanged.connect(window.engine.retranslate)

    # Qt's warnings and any uncaught exception used to go only to a console a
    # windowed build does not have (see python/log_capture.py). Installed before
    # the QML loads, so engine-level complaints land in the Log page too.
    vm.install_log_capture()

    window.load(ROOT / "qml" / "MainWindow.qml")

    # Windows answers the top edge of a fullscreen window as a resize border
    # (HTTOP), so the fullscreen Zen strip's top pixels — the ones the pointer
    # reaches the strip at — never see the mouse at all. Installed after the
    # load because RinUI installs its own native filter there and filters run
    # last-installed-first. See python/window_drag.py.
    window_drag.install_fullscreen_hit_test()

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
