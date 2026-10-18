# coding: utf-8
"""Calculator viewmodel for the QML Symplify app.

Exposes the Calculator model to QML through typed properties and slots.
The widgets app's eager plot-data computation (``create_plot_data`` /
``compute_plot_data``) and legacy assignment path are not carried over.
"""

from typing import Any, List, Optional

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QColor
from qmlmathplot import Curve, ImplicitCurve, Plot

from ..latex_render import LatexStyle, render_data_url
from ..model.calculator import Assignment, Calculator, ErrorKind, Failure, Result, Success
from ..model.plotting import is_plot_variable, plot_series, plot_variable_warning
from ..model.variable import VariableManager
from .history_viewmodel import HistoryModel
from .input_mode import InputMode
from .log_viewmodel import LogViewModel

#: The plot's theme, per UI side: Matplotlib's own default and its
#: `dark_background` counterpart (qmlmathplot ships both as style sheets). The
#: plot follows the app's theme (the window re-applies this on every switch), and
#: the theme name is the whole of that: the style owns its colours, so nothing
#: here paints over them.
PLOT_THEMES = {False: "default", True: "dark_background"}


class CalculatorViewModel(QObject):
    """Connects the Calculator model to the QML calculator page.

    Signals:
        inputModeChanged: Emitted when the input mode changes.
        plotChanged: Emitted when the plot's curves or its error changed.
        warningOccurred: Emitted when the user assigns to a SymPy built-in or to
            a plotting variable.
            Args:
                title (str): Warning title.
                content (str): Warning content.
    """

    inputModeChanged = Signal()
    inputTextChanged = Signal()
    assignInputChanged = Signal()
    resultChanged = Signal()
    plotChanged = Signal()
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
        #: Theme ink, font size and LaTeX font file, in one value; built by
        #: `MainViewModel`, which owns the settings and sees the theme.
        self._latex_style = LatexStyle()
        # The plot is state that has to survive a page switch — RinUI rebuilds
        # pages on every navigation — so it lives here, and the page injects it
        # into its `PlotView`. The curves are its children and outlive the page
        # with it.
        self._plot = Plot(parent=self)
        # Square units: one world unit is the same length on both axes, so a circle
        # draws round and a slope reads as its value. The camera then shows more
        # canvas when the area grows instead of stretching what is drawn.
        self._plot.aspect = 1.0
        # The built-in legend names the labelled curves (`f`, `f′`) and is part of
        # the scene, so an export carries it too. qmlmathplot starts without one;
        # everything we draw is labelled, so it is always wanted.
        self._plot.legend = True
        self._curves: List[Curve] = []
        self._series: tuple = ()
        self._plot_error = ""
        # A fresh page has nothing to typeset: the formula area stays empty and the
        # outcome box above it carries the placeholder.
        self._refresh_strip()

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
        """Render LaTeX for the formula area, storing its data URL and size."""
        self._latex_svg_url, self._latex_width, self._latex_height = render_data_url(
            latex, self._latex_style
        )
        return self._latex_svg_url

    def _clear_latex(self) -> None:
        """Empty the formula area's artwork."""
        self._latex_svg_url = ""
        self._latex_width = 0
        self._latex_height = 0

    def _refresh_strip(self) -> None:
        """Decide what the formula area holds, and render it.

        The result's own LaTeX, or nothing at all: the area is the formula's alone,
        and the outcome line above carries whatever there is to *read* — a value, a
        failure, or the placeholder. (The empty state used to be typeset here, which
        turned a sentence into artwork and put the placeholder where the formula
        goes.)
        """
        if self._result_latex:
            self._build_latex_url(self._result_latex)
        else:
            self._clear_latex()

    def set_latex_style(self, style: LatexStyle) -> None:
        """Re-render the current result in a new style.

        One entry point for the three knobs: they all mean "draw it again", and
        they now arrive together — the theme owns the ink, the settings store the
        size and the font file, and `MainViewModel` assembles both into one
        `LatexStyle`. The data URL changes, so the `Image` refreshes itself.
        """
        if style == self._latex_style:
            return
        self._latex_style = style
        self._refresh_strip()
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

    def _get_plot(self) -> Plot:
        """The plot the calculator page renders; owned here, so it survives pages."""
        return self._plot

    plot = Property(QObject, _get_plot, constant=True)

    def _get_has_plot(self) -> bool:
        """True while there is something to draw (the page hides the area otherwise)."""
        return bool(self._curves)

    hasPlot = Property(bool, _get_has_plot, notify=plotChanged)

    def _get_plot_error(self) -> str:
        """The first curve's shader error, or '' — a failed bake must be visible."""
        return self._plot_error

    plotError = Property(str, _get_plot_error, notify=plotChanged)

    @Slot(bool)
    def setPlotTheme(self, dark: bool) -> None:
        """Use the seaborn style that belongs to the UI's current side.

        Called by the window on start-up and after every theme switch (RinUI
        rebuilds the theme object on one, so a binding would not survive). The
        style sheet owns the plot's colours; this sets the name and nothing else.
        """
        theme = PLOT_THEMES[bool(dark)]
        if theme == self._plot.theme:
            return
        self._plot.theme = theme
        # Each style brings its own colour cycle (tab10 against
        # dark_background's bright set) and a curve keeps the colour it was
        # given — so re-dress what is already drawn, or the palette and the
        # legend would disagree with the new theme.
        if self._series:
            self._set_plot(self._series)

    def _colour(self, index: int) -> str:
        """The cycle colour for slot ``index``, as the string a curve takes."""
        cycle = self._plot.color_cycle
        return cycle[index % len(cycle)] if cycle else ""

    def _set_plot(self, series: tuple) -> None:
        """Reconcile the plot's curves with ``series``.

        Curves are reused slot by slot, so recalculating the same shape only
        changes the expressions — and qmlmathplot's bake cache makes that nearly
        free. A slot whose artist changes kind (explicit ↔ implicit) is rebuilt,
        because the two are different classes. Nothing here may raise: a plotting
        failure is a log line and the card's error text, not a broken Qt slot.
        """
        self._series = series
        try:
            # The longest prefix that can be updated in place.
            keep = 0
            while keep < min(len(self._curves), len(series)):
                if isinstance(self._curves[keep], ImplicitCurve) != series[keep].implicit:
                    break
                keep += 1
            while len(self._curves) > keep:
                self._plot.remove_curve(self._curves.pop())
            for index, item in enumerate(series):
                colour = self._colour(index)
                if index < keep:
                    curve = self._curves[index]
                    curve.expression = item.expression
                    curve.label = item.label
                    curve.color = colour
                    continue
                add = self._plot.add_implicit if item.implicit else self._plot.add_curve
                self._curves.append(add(item.expression, colour, None, item.label))
            error = next((curve.error for curve in self._curves if curve.error), "")
        except Exception as exc:  # noqa: BLE001 - a plot must not break the result
            error = f"{type(exc).__name__}: {exc}"
            for curve in list(self._curves):
                self._plot.remove_curve(curve)
            self._curves.clear()
        if error and error != self._plot_error:
            self._log.add_warning(f"Plot failed: {error}", "Calculator")
        self._plot_error = error
        self.plotChanged.emit()

    @Slot()
    def clear_result(self) -> None:
        """Clear the result display area (the outcome box then shows the placeholder)."""
        self._result_text = ""
        self._result_latex = ""
        self._is_error = False
        self._error_message = ""
        self._set_plot(())
        self._refresh_strip()
        self.resultChanged.emit()

    def _apply_result(self, result: Result) -> None:
        """Apply a request's outcome to the exposed display properties."""
        if isinstance(result, Success):
            self._result_text = str(result.value)
            self._result_latex = result.latex
            self._is_error = False
            self._error_message = ""
            self._set_plot(plot_series(result.value, result.origin))
        else:
            self._result_text = ""
            self._result_latex = ""
            self._is_error = True
            self._error_message = self._format_failure(result)
            self._set_plot(())
        self._refresh_strip()
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
        self._log.add_info(expression, "Calculator")
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
        self._log.add_info(f"{name} {operator} {value_str}", "Calculator")
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
        """Save an assigned variable, warning about the names input depends on."""
        try:
            if self._variables_model is not None:
                self._variables_model.save(name, value)
        except Exception as e:
            self._log.add_warning(f"Failed to save variable: {e}", "Calculator")

        if VariableManager.is_sympy_builtin(name):
            self.warningOccurred.emit(
                name, f"{name} is a SymPy built-in. You asked for it."
            )
        elif is_plot_variable(name):
            self.warningOccurred.emit(name, plot_variable_warning(name))
