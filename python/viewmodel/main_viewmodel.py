# coding: utf-8
"""Root viewmodel for the QML Symplify app.

Aggregates the sub-viewmodels and is exposed to QML as the ``vm``
context property.
"""

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QEvent,
    QObject,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication, QKeyEvent
from typing import Optional

from ..model.calculator import Calculator
from ..model.variable import VariableManager
from ..settings import SettingsStore
from .calculator_viewmodel import CalculatorViewModel
from .history_viewmodel import HistoryModel
from .log_viewmodel import LogViewModel
from .search import HistoryFilterModel, VariablesFilterModel
from .settings_viewmodel import SettingsViewModel
from .variables_viewmodel import VariablesViewModel


class MainViewModel(QObject):
    """Holds the shared models and exposes all sub-viewmodels to QML.

    Signals:
        sendToCode: Requested by the history page to restore a code entry
            in the calculator's Code input. Args: expression (str).
        sendToAssign: Requested by the history page to restore an assign
            entry in the calculator's Assign input. Args:
            name (str), operator (str), expression (str).
    """

    sendToCode = Signal(str)
    sendToAssign = Signal(str, str, str)

    def __init__(
        self,
        settings: SettingsStore,
        theme_manager: Optional[QObject] = None,
        parent: Optional[QObject] = None,
    ):
        """Initialize all models and viewmodels.

        Args:
            settings: The loaded settings store (single source of truth).
            theme_manager: RinUI's ``ThemeManager``, so the settings viewmodel can
                apply appearance changes; None in headless tests.
        """
        super().__init__(parent)
        self._calculator = Calculator()
        self._variable_manager = VariableManager()

        self._history = HistoryModel(parent=self)
        self._log = LogViewModel(parent=self)
        self._variables_vm = VariablesViewModel(
            self._variable_manager, self._log, self._calculator, parent=self
        )
        self._calculator_vm = CalculatorViewModel(
            self._calculator,
            self._variable_manager,
            self._history,
            self._log,
            variables_model=self._variables_vm.model,
            parent=self,
        )

        # Search-filtered views: the pages bind their views to these, so the
        # source models keep every entry regardless of an active query.
        self._variables_filter = VariablesFilterModel(parent=self)
        self._variables_filter.setSourceModel(self._variables_vm.model)
        self._history_filter = HistoryFilterModel(parent=self)
        self._history_filter.setSourceModel(self._history)

        self._settings = SettingsViewModel(settings, theme_manager, parent=self)
        self._settings.latexSizeChanged.connect(self._apply_latex_size)
        self._apply_latex_size()      # apply the persisted rendering settings now

    def _apply_latex_size(self) -> None:
        """Push the configured result font size to everything that renders LaTeX."""
        size = self._settings.latexSize
        self._calculator_vm.set_latex_size(size)
        self._history.set_latex_size(size)

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

    @Property(QObject, constant=True)
    def variablesFilter(self) -> VariablesFilterModel:
        """Search-filtered view of the variables table."""
        return self._variables_filter

    @Property(QObject, constant=True)
    def historyFilter(self) -> HistoryFilterModel:
        """Search-filtered view of the history cards."""
        return self._history_filter

    @Property(QObject, constant=True)
    def settings(self) -> SettingsViewModel:
        """The settings viewmodel (appearance, rendering, window, config path)."""
        return self._settings

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
