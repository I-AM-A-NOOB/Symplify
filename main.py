# coding: utf-8
"""Entry point for the QML Symplify app.

Runs the Fluent WinUI 3-styled QML user interface using native Qt Quick
Controls only (no qfluentwidgets). Business logic lives in the pure-Python
``python/`` package, exposed to QML through viewmodels.

Usage:
    python main.py
"""

import os
import sys
from pathlib import Path

# The Qt Quick Controls style must be selected before QGuiApplication is created.
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "FluentWinUI3")

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from python.keyboard_config import load_keyboard_tabs  # noqa: E402
from python.viewmodel.main_viewmodel import MainViewModel  # noqa: E402


def main() -> int:
    """Run the QML prototype."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Symplify QML")
    app.setApplicationDisplayName("Symplify (QML prototype)")

    vm = MainViewModel()

    engine = QQmlApplicationEngine()
    # Child viewmodels/models are exposed as flat context properties so pages
    # never chain through `vm.<child>`, which can transiently fail to resolve
    # on some platforms during initial SwipeView delegate creation.
    engine.rootContext().setContextProperty("vm", vm)
    engine.rootContext().setContextProperty("calcVM", vm.calculator)
    engine.rootContext().setContextProperty("varsVM", vm.variables)
    engine.rootContext().setContextProperty("variablesModel", vm.variables.model)
    engine.rootContext().setContextProperty("historyVM", vm.history)
    engine.rootContext().setContextProperty("logVM", vm.log)
    engine.rootContext().setContextProperty("keyboardTabs", load_keyboard_tabs())

    engine.load(QUrl.fromLocalFile(str(ROOT / "qml" / "MainWindow.qml")))
    if not engine.rootObjects():
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
