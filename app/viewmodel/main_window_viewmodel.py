# coding: utf-8
"""Main Window ViewModel for the Symplify application.

This module provides the ViewModel for the main window,
managing application-level state and coordination between sub-viewmodels.

Example:
    >>> from app.viewmodel import MainWindowViewModel
    >>> from app.model import Calculator, VariableManager
    >>> vm = MainWindowViewModel(Calculator(), VariableManager())
"""
from typing import Optional

from PySide6.QtCore import QObject, Signal

from ..model.calculator import Calculator
from ..model.variable import VariableManager
from .calculator_viewmodel import CalculatorViewModel
from .variables_viewmodel import VariablesViewModel
from .history_viewmodel import HistoryViewModel
from .log_viewmodel import LogViewModel


class MainWindowViewModel(QObject):
    """ViewModel for the main window.

    Manages application-level coordination between sub-viewmodels.
    Sub-viewmodels can be accessed directly for their specific methods.

    Signals:
        log_updated: Emitted when log content changes.
        history_updated: Emitted when history changes.

    Attributes:
        calculator_viewmodel: The Calculator ViewModel.
        variables_viewmodel: The Variables ViewModel.
        history_viewmodel: The History ViewModel.
        log_viewmodel: The Log ViewModel.

    Example:
        >>> vm = MainWindowViewModel(Calculator(), VariableManager())
        >>> vm.calculator_viewmodel.calculate("2 + 2")
    """

    log_updated = Signal(str)
    history_updated = Signal()

    def __init__(
        self,
        calculator: Calculator,
        variable_manager: VariableManager,
        parent: Optional[QObject] = None,
    ):
        """Initialize the main window ViewModel.

        Args:
            calculator: The Calculator model instance.
            variable_manager: The VariableManager model instance.
            parent: Optional parent QObject.
        """
        super().__init__(parent)

        # Create shared ViewModels
        self.log_viewmodel = LogViewModel(parent=self)
        self.history_viewmodel = HistoryViewModel(parent=self)

        # Create sub-viewmodels with shared dependencies
        self.calculator_viewmodel = CalculatorViewModel(
            calculator,
            variable_manager,
            self.log_viewmodel,
            self.history_viewmodel,
            parent=self,
        )
        self.variables_viewmodel = VariablesViewModel(
            variable_manager, self.log_viewmodel, parent=self
        )

        # Connect signals
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect ViewModel signals."""
        # Log updates - forward to main window
        self.log_viewmodel.log_updated.connect(self._on_log_updated)
        self.log_viewmodel.log_cleared.connect(self._on_log_cleared)

        # History updates - forward to main window
        self.history_viewmodel.history_updated.connect(self._on_history_updated)

    def _on_log_updated(self, entry) -> None:
        """Forward log update to main window."""
        self.log_updated.emit(self.log_viewmodel.get_formatted_logs())

    def _on_log_cleared(self) -> None:
        """Forward log cleared to main window."""
        self.log_updated.emit("")

    def _on_history_updated(self) -> None:
        """Forward history update to main window."""
        self.history_updated.emit()

    def add_variable_with_default(self) -> tuple[str, bool]:
        """Add a variable with default name and value.

        Returns:
            Tuple of (variable_name, success).
        """
        name = self.variables_viewmodel.generate_unique_name("var")
        success = self.variables_viewmodel.add_variable(name, 0)
        return name, success
