# coding: utf-8
"""Root viewmodel for the QML Symplify app.

Aggregates the sub-viewmodels and is exposed to QML as the ``vm``
context property.
"""

from PySide6.QtCore import Property, QCoreApplication, QEvent, QObject, Qt, Slot
from PySide6.QtGui import QGuiApplication, QKeyEvent

from ..model.calculator import Calculator
from ..model.variable import VariableManager
from .calculator_viewmodel import CalculatorViewModel
from .history_viewmodel import HistoryModel
from .log_viewmodel import LogViewModel
from .variables_viewmodel import VariablesViewModel


class MainViewModel(QObject):
    """Holds the shared models and exposes all sub-viewmodels to QML."""

    def __init__(self, parent=None):
        """Initialize all models and viewmodels."""
        super().__init__(parent)
        self._calculator = Calculator()
        self._variable_manager = VariableManager()

        self._history = HistoryModel(parent=self)
        self._log = LogViewModel(parent=self)
        self._variables_vm = VariablesViewModel(
            self._variable_manager, self._log, parent=self
        )
        self._calculator_vm = CalculatorViewModel(
            self._calculator,
            self._variable_manager,
            self._history,
            self._log,
            variables_model=self._variables_vm.model,
            parent=self,
        )

    @Property(QObject, constant=True)
    def calculator(self) -> CalculatorViewModel:
        """The calculator viewmodel."""
        return self._calculator_vm

    @Property(QObject, constant=True)
    def variables(self) -> VariablesViewModel:
        """The variables viewmodel."""
        return self._variables_vm

    @Property(QObject, constant=True)
    def history(self) -> HistoryModel:
        """The history model."""
        return self._history

    @Property(QObject, constant=True)
    def log(self) -> LogViewModel:
        """The log viewmodel."""
        return self._log

    @Slot(str)
    def copyText(self, text: str) -> None:
        """Copy ``text`` to the system clipboard."""
        QGuiApplication.clipboard().setText(text)

    @Slot()
    def focusNext(self) -> None:
        """Move focus to the next control (Ctrl+Tab), using native focus order."""
        self._send_tab(Qt.KeyboardModifier.NoModifier)

    @Slot()
    def focusPrev(self) -> None:
        """Move focus to the previous control (Ctrl+Shift+Tab)."""
        self._send_tab(Qt.KeyboardModifier.ShiftModifier)

    def _send_tab(self, modifiers: Qt.KeyboardModifier) -> None:
        """Synthesize a Tab key press to trigger Qt's native focus navigation.

        This works for any focused control (now and in the future) without
        hard-coding a focus chain, unlike per-control KeyNavigation.
        """
        win = QGuiApplication.focusWindow()
        if win is None:
            tops = QGuiApplication.topLevelWindows()
            win = tops[0] if tops else None
        if win is None:
            return
        press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, modifiers)
        release = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Tab, modifiers)
        QCoreApplication.sendEvent(win, press)
        QCoreApplication.sendEvent(win, release)
