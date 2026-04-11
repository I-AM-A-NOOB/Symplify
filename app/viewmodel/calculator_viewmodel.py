# coding: utf-8
"""Calculator ViewModel for the Symplify application.

This module provides the ViewModel for the calculator interface,
connecting the Calculator model with the CalculatorInterface view.
Uses EventBus for decoupled communication.

Example:
    >>> from app.model import Calculator, VariableManager
    >>> from app.viewmodel import CalculatorViewModel, LogViewModel, HistoryViewModel
    >>> calc = Calculator()
    >>> vm = CalculatorViewModel(calc, VariableManager(), LogViewModel(), HistoryViewModel())
    >>> vm.calculate("x**2", InputMode.CODE)
"""

from typing import Optional, Tuple, Any

from PySide6.QtCore import QObject, Signal

from ..model.calculator import Calculator, CalculationResult, ResultType
from ..model.variable import VariableManager
from ..common.event_bus import event_bus, Events
from ..common.input_mode import InputMode
from .log_viewmodel import LogViewModel
from .history_viewmodel import HistoryViewModel


class CalculatorViewModel(QObject):
    """ViewModel for the calculator interface.

    Connects the Calculator model with the CalculatorInterface view.
    Uses EventBus to notify other components of variable changes.
    Delegates log and history management to separate ViewModels.

    Signals:
        result_ready: Emitted when calculation completes.
        plot_ready: Emitted when plot data is ready.
            Args:
                expr: The SymPy expression to plot.
                var_range: Tuple of (symbol, min, max).
        error_occurred: Emitted when calculation fails.

    Attributes:
        calculator: The Calculator model instance.
        variable_manager: The VariableManager model instance.
        log_viewmodel: The Log ViewModel for logging.
        history_viewmodel: The History ViewModel for history.

    Example:
        >>> vm = CalculatorViewModel(Calculator(), VariableManager(), LogViewModel(), HistoryViewModel())
        >>> vm.result_ready.connect(view.show_result)
        >>> vm.calculate("2 + 2", InputMode.CODE)
    """

    result_ready = Signal(CalculationResult)
    error_occurred = Signal(str)

    def __init__(
        self,
        calculator: Calculator,
        variable_manager: VariableManager,
        log_viewmodel: LogViewModel,
        history_viewmodel: HistoryViewModel,
        parent: Optional[QObject] = None,
    ):
        """Initialize the calculator ViewModel.

        Args:
            calculator: The Calculator model instance.
            variable_manager: The VariableManager model instance.
            log_viewmodel: The Log ViewModel for logging.
            history_viewmodel: The History ViewModel for history.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._calculator = calculator
        self._variable_manager = variable_manager
        self._log_viewmodel = log_viewmodel
        self._history_viewmodel = history_viewmodel

    def calculate(self, expression: str, mode: InputMode) -> None:
        """Perform calculation based on input mode.

        Calculates the expression, creates plot data, and emits result.
        The result includes both LaTeX representation and plot data.

        Args:
            expression: The expression to evaluate.
            mode: The input mode (CODE or ASSIGN).

        Example:
            >>> vm.calculate("2 + 2", InputMode.CODE)
            >>> vm.calculate("x = 42", InputMode.ASSIGN)
        """
        self._log_viewmodel.add_info(f"> {expression}", "Calculator")

        try:
            if mode == InputMode.CODE:
                result = self._calculate_code(expression)
            else:
                result = self._calculate_assign(expression)

            if result.success:
                # Create plot data and compute data points
                plot_data = self._calculator.create_plot_data(result.value)
                if plot_data:
                    plot_model = self._calculator.get_plot_model()
                    result.data_points = plot_model.compute_plot_data(plot_data)

                # Add to history
                self._history_viewmodel.add_item(expression, result, mode)

                # Emit result (includes LaTeX and data points)
                self.result_ready.emit(result)

                self._log_viewmodel.add_info(f"= {result.value}", "Calculator")
            else:
                self.error_occurred.emit(result.error)
                self._log_viewmodel.add_error(f"Error: {result.error}", "Calculator")

        except Exception as e:
            self.error_occurred.emit(str(e))
            self._log_viewmodel.add_error(f"Error: {e}", "Calculator")

    def _calculate_code(self, expression: str) -> CalculationResult:
        """Calculate in code mode.

        Args:
            expression: The expression to evaluate.

        Returns:
            The calculation result.
        """
        return self._calculator.evaluate(expression, self._variable_manager.list_all())

    def _calculate_assign(self, expression: str) -> CalculationResult:
        """Calculate in assignment mode.

        Args:
            expression: The assignment expression (e.g., "x = 2 + 2").

        Returns:
            The calculation result.
        """
        result = self._calculator.evaluate_assignment(
            expression, self._variable_manager.list_all()
        )

        if result.success and result.result_type == ResultType.ASSIGNMENT:
            # Get variable info from metadata
            var_name = result.metadata.get("variable_name", "")
            var_value = result.metadata.get("variable_value")

            # Save to VariableManager
            try:
                self._variable_manager.set(var_name, var_value)
            except Exception as e:
                self._log_viewmodel.add_warning(
                    f"Failed to save variable: {e}", "Calculator"
                )

            # Publish event to notify other ViewModels
            event_bus.publish(
                Events.VARIABLE_ADDED,
                {"name": var_name, "value": var_value},
            )

        return result

    def get_latex(self, expression: str) -> str:
        """Get LaTeX representation of an expression.

        Args:
            expression: The expression to convert.

        Returns:
            LaTeX string representation.

        Example:
            >>> vm.get_latex("x**2 + 1")
            'x^{2} + 1'
        """
        try:
            import sympy as sp

            expr = sp.sympify(expression, locals=self._variable_manager.list_all())
            return sp.latex(expr)
        except Exception:
            return expression

    def clear_history(self) -> None:
        """Clear calculation history."""
        self._history_viewmodel.clear()
        self._log_viewmodel.add_info("History cleared", "Calculator")

    def get_log(self) -> str:
        """Get full log content.

        Returns:
            Log content as string.
        """
        return self._log_viewmodel.get_formatted_logs()

    def clear_log(self) -> None:
        """Clear the log."""
        self._log_viewmodel.clear()
