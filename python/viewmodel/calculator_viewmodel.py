# coding: utf-8
"""Calculator viewmodel for the QML Symplify app.

Exposes the Calculator model to QML through typed properties and slots.
The widgets app's eager plot-data computation (``create_plot_data`` /
``compute_plot_data``) and legacy assignment path are not carried over.
"""

from typing import Any, Optional
from urllib.parse import quote

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QColor

from ..latex_render import latex_to_svg, svg_size
from ..model.calculator import Assignment, Calculator, ErrorKind, Failure, Result, Success
from ..model.variable import VariableManager
from .history_viewmodel import HistoryModel
from .input_mode import InputMode
from .log_viewmodel import LogViewModel


class CalculatorViewModel(QObject):
    """Connects the Calculator model to the QML calculator page.

    Signals:
        inputModeChanged: Emitted when the input mode changes.
        warningOccurred: Emitted when the user assigns to a SymPy built-in.
            Args:
                title (str): Warning title.
                content (str): Warning content.
    """

    inputModeChanged = Signal()
    inputTextChanged = Signal()
    assignInputChanged = Signal()
    resultChanged = Signal()
    warningOccurred = Signal(str, str)

    def __init__(
        self,
        calculator: Calculator,
        variable_manager: VariableManager,
        history: HistoryModel,
        log: LogViewModel,
        variables_model: Optional["VariablesModel"] = None,
        parent: Optional[QObject] = None,
    ):
        """Initialize the calculator viewmodel.

        Args:
            variables_model: The shared variables model, refreshed when an
                assignment saves a new variable (optional).
        """
        super().__init__(parent)
        self._calculator = calculator
        self._variable_manager = variable_manager
        self._history = history
        self._log = log
        self._variables_model = variables_model
        self._input_mode = InputMode.CODE
        self._input_text = ""
        self._assign_name = ""
        self._assign_operator = "="
        self._assign_value = ""
        self._result_text = ""
        self._result_latex = ""
        self._is_error = False
        self._error_message = ""
        self._latex_svg_url = ""
        self._latex_width = 0
        self._latex_height = 0
        self._latex_color = "#000000"
        self._latex_size = 24
        #: Path to the LaTeX font file; '' uses ziamath's bundled font.
        self._latex_font = ""

    def _get_input_mode(self) -> int:
        """Current input mode as a stable int (InputMode.CODE.value)."""
        return int(self._input_mode.value)

    def _set_input_mode(self, mode: int) -> None:
        """Set the input mode from a QML int, notifying on change."""
        new_mode = InputMode(mode)
        if new_mode != self._input_mode:
            self._input_mode = new_mode
            self.inputModeChanged.emit()

    def _get_input_text(self) -> str:
        return self._input_text

    def _set_input_text(self, text: str) -> None:
        """Persist the code-mode expression across page rebuilds."""
        if text != self._input_text:
            self._input_text = text
            self.inputTextChanged.emit()

    def _get_assign_name(self) -> str:
        return self._assign_name

    def _set_assign_name(self, name: str) -> None:
        if name != self._assign_name:
            self._assign_name = name
            self.assignInputChanged.emit()

    def _get_assign_operator(self) -> str:
        return self._assign_operator

    def _set_assign_operator(self, operator: str) -> None:
        if operator != self._assign_operator:
            self._assign_operator = operator
            self.assignInputChanged.emit()

    def _get_assign_value(self) -> str:
        return self._assign_value

    def _set_assign_value(self, value: str) -> None:
        if value != self._assign_value:
            self._assign_value = value
            self.assignInputChanged.emit()

    def _get_result_text(self) -> str:
        return self._result_text

    def _get_result_latex(self) -> str:
        return self._result_latex

    def _get_is_error(self) -> bool:
        return self._is_error

    def _get_error_message(self) -> str:
        return self._error_message

    def _get_latex_svg_url(self) -> str:
        """Data URL of the rendered LaTeX SVG, or '' if unavailable."""
        return self._latex_svg_url

    def _get_latex_width(self) -> int:
        return self._latex_width

    def _get_latex_height(self) -> int:
        return self._latex_height

    def _build_latex_url(self, latex: str) -> str:
        """Render LaTeX to an SVG data URL, storing its intrinsic size."""
        svg = latex_to_svg(
            latex,
            size=self._latex_size,
            color=self._latex_color,
            font=self._latex_font,
        )
        if not svg:
            self._latex_svg_url = ""
            self._latex_width = 0
            self._latex_height = 0
            return ""
        self._latex_svg_url = "data:image/svg+xml;charset=utf-8," + quote(svg, safe="")
        self._latex_width, self._latex_height = svg_size(svg)
        return self._latex_svg_url

    @Slot(str)
    def set_latex_color(self, color: str) -> None:
        """Re-tint the rendered LaTeX (called when the RinUI theme changes).

        Re-renders the current result with the new color; the Image element
        refreshes automatically because the data URL changes.
        """
        qcolor = QColor(color)
        if not qcolor.isValid():
            return
        normalized = qcolor.name()
        if normalized == self._latex_color:
            return
        self._latex_color = normalized
        if self._result_latex:
            self._build_latex_url(self._result_latex)
            self.resultChanged.emit()

    @Slot(int)
    def set_latex_size(self, size: int) -> None:
        """Re-render the current result at a new font size (settings page).

        Mirrors :meth:`set_latex_color`: the value comes from the settings store
        and only the rendering changes, so the data URL is rebuilt in place.
        """
        size = int(size)
        if size == self._latex_size:
            return
        self._latex_size = size
        if self._result_latex:
            self._build_latex_url(self._result_latex)
            self.resultChanged.emit()

    @Slot(str)
    def set_latex_font(self, font: str) -> None:
        """Re-render the current result with a different LaTeX font.

        Mirrors :meth:`set_latex_size`; ``font`` is a font file path (or '' for
        ziamath's bundled font), resolved by ``python/fonts.py``.
        """
        font = font or ""
        if font == self._latex_font:
            return
        self._latex_font = font
        if self._result_latex:
            self._build_latex_url(self._result_latex)
            self.resultChanged.emit()

    inputMode = Property(
        int, _get_input_mode, _set_input_mode, notify=inputModeChanged
    )
    inputText = Property(str, _get_input_text, _set_input_text, notify=inputTextChanged)
    assignName = Property(
        str, _get_assign_name, _set_assign_name, notify=assignInputChanged
    )
    assignOperator = Property(
        str, _get_assign_operator, _set_assign_operator, notify=assignInputChanged
    )
    assignValue = Property(
        str, _get_assign_value, _set_assign_value, notify=assignInputChanged
    )
    resultText = Property(str, _get_result_text, notify=resultChanged)
    resultLatex = Property(str, _get_result_latex, notify=resultChanged)
    isError = Property(bool, _get_is_error, notify=resultChanged)
    errorMessage = Property(str, _get_error_message, notify=resultChanged)
    latexSvgUrl = Property(str, _get_latex_svg_url, notify=resultChanged)
    latexWidth = Property(int, _get_latex_width, notify=resultChanged)
    latexHeight = Property(int, _get_latex_height, notify=resultChanged)

    @Slot()
    def clear_result(self) -> None:
        """Clear the result display area."""
        self._result_text = ""
        self._result_latex = ""
        self._is_error = False
        self._error_message = ""
        self._latex_svg_url = ""
        self._latex_width = 0
        self._latex_height = 0
        self.resultChanged.emit()

    def _apply_result(self, result: Result) -> None:
        """Apply a request's outcome to the exposed display properties."""
        if isinstance(result, Success):
            self._result_text = str(result.value)
            self._result_latex = result.latex
            self._is_error = False
            self._error_message = ""
            self._latex_svg_url = self._build_latex_url(result.latex)
        else:
            self._result_text = ""
            self._result_latex = ""
            self._is_error = True
            self._error_message = self._format_failure(result)
            self._latex_svg_url = ""
            self._latex_width = 0
            self._latex_height = 0
        self.resultChanged.emit()

    @staticmethod
    def _format_failure(failure: Failure) -> str:
        """User-facing error text: the message plus its hint, when there is one."""
        if failure.hint:
            return f"{failure.message} — {failure.hint}"
        return failure.message

    @Slot(str)
    def calculate(self, expression: str) -> None:
        """Evaluate an expression in code mode."""
        self._log.add_info(f"> {expression}", "Calculator")
        result = self._calculator.evaluate(
            expression, self._variable_manager.list_all()
        )
        self._apply_result(result)
        if isinstance(result, Success):
            self._history.add_item(
                expression, self._result_text, "Code", latex=result.latex
            )
            self._log.add_info(f"= {result.value}", "Calculator")
        else:
            # Failures are part of the history too: keeping the input and the
            # failure text is what lets a typo be sent back and fixed.
            self._history.add_item(
                expression, "", "Code", error=self._format_failure(result)
            )
            self._log.add_error(f"Error: {result.message}", "Calculator")

    @Slot(str, str, str)
    def calculateAssign(self, name: str, operator: str, value_str: str) -> None:
        """Answer an assignment in assign mode.

        The model validates the target before evaluating anything, so a rejected
        write never reaches the history, the "= value" log line or the variable
        store. An unparsable value is still kept as an invalid (NaN) entry, so
        the user's input survives.
        """
        self._log.add_info(f"> {name} {operator} {value_str}", "Calculator")
        result = self._calculator.assign(
            Assignment(name, operator, value_str),
            self._variable_manager.list_all(),
        )
        self._apply_result(result)

        if isinstance(result, Success):
            self._history.add_item(
                value_str,
                self._result_text,
                "Assign",
                latex=result.latex,
                name=name,
                op=operator,
            )
            self._save_variable(name, result.value)
            self._log.add_info(f"= {result.value}", "Calculator")
            return

        self._history.add_item(
            value_str,
            "",
            "Assign",
            name=name,
            op=operator,
            error=self._format_failure(result),
        )
        self._log.add_error(f"Error: {result.message}", "Calculator")
        if result.kind is ErrorKind.INVALID_NAME:
            return
        if operator == "=" and self._variables_model is not None:
            try:
                self._variables_model.save_invalid(name, value_str)
            except Exception as e:
                self._log.add_warning(
                    f"Failed to store invalid entry: {e}", "Calculator"
                )

    def _save_variable(self, name: str, value: Any) -> None:
        """Save an assigned variable, warning about SymPy built-ins."""
        try:
            if self._variables_model is not None:
                self._variables_model.save(name, value)
        except Exception as e:
            self._log.add_warning(f"Failed to save variable: {e}", "Calculator")

        if VariableManager.is_sympy_builtin(name):
            self.warningOccurred.emit(
                name, f"{name} is a SymPy built-in. You asked for it."
            )
