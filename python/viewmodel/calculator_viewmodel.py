"""Calculator viewmodel for the QML Symplify app.

Exposes the Calculator model to QML through typed properties and slots.
The widgets app's eager plot-data computation (``create_plot_data`` /
``compute_plot_data``) and legacy assignment path are not carried over.
"""

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QCoreApplication, QObject, QTimer, Signal, Slot
from qmlmathplot import Curve, ImplicitCurve, Plot
from qmlmathplot.model import func_glsl

from ..latex_render import LatexStyle
from ..model.calculator import Assignment, ErrorKind, Failure, Result, Success
from ..model.plotting import is_plot_variable, plot_series, plot_variable_warning
from ..model.variable import VariableManager
from ..model.variants import Variant
from .calculation_backend import InlineBackend
from .history_viewmodel import HistoryModel
from .input_mode import InputMode
from .latex_service import LatexRenderService
from .log_viewmodel import LogViewModel

if TYPE_CHECKING:
    from .variables_viewmodel import VariablesModel

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
    variantsChanged = Signal()
    plotChanged = Signal()
    warningOccurred = Signal(str, str)
    #: ``backendBusy`` / ``backendStatus`` changed.
    backendStateChanged = Signal()

    def __init__(
        self,
        variable_manager: VariableManager,
        history: HistoryModel,
        log: LogViewModel,
        variables_model: VariablesModel | None = None,
        parent: QObject | None = None,
        backend: QObject | None = None,
        latex_service: LatexRenderService | None = None,
    ):
        """Initialize the calculator viewmodel.

        Args:
            variables_model: The shared variables model, refreshed when an
                assignment saves a new variable (optional).
            backend: Calculation transport. None keeps the synchronous in-process
                backend (tests/headless); the application passes a process
                backend with a timeout.
            latex_service: Renderer shared with History. None creates one; with
                no QCoreApplication it renders inline.
        """
        super().__init__(parent)
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
        #: Alternative forms of the current answer; their artwork is filled by
        #: the renderer as each request completes.
        self._variants: tuple[Variant, ...] = ()
        self._variant_items: list[dict] = []
        #: Tokens handed to `LatexRenderService`, mapped to their display target
        #: (`("result", -1)` or `("variant", row)`). A new result or style
        #: clears the map, which makes late completions stale.
        self._latex_pending: dict[str, tuple[str, int]] = {}
        self._latex_seq = 0
        #: Calculation crosses a backend boundary. The default is synchronous
        #: (tests, headless callers); the application passes a process backend
        #: with a timeout. The viewmodel allocates request ids, so both take the
        #: same path and stale replies are ignored.
        self._backend = backend if backend is not None else InlineBackend(self)
        self._backend.finished.connect(self._on_backend_finished)
        self._backend.variantsReady.connect(self._on_variants_ready)
        self._backend.timedOut.connect(self._on_backend_timed_out)
        self._backend.failed.connect(self._on_backend_failed)
        self._request_seq = 0
        self._active_request: int | None = None
        self._pending: dict | None = None
        #: The request whose result is displayed. Only its late variant rows may
        #: be applied; a new request clears it immediately.
        self._last_completed_request: int | None = None
        self._backend_busy = False
        self._backend_status = "ready"
        #: Theme ink, font size and LaTeX font file, in one value; built by
        #: `MainViewModel`, which owns the settings and sees the theme.
        self._latex_style = LatexStyle()
        # One renderer process shared with History. With no QApplication the
        # service renders inline, keeping the tests free of event-loop setup.
        self._latex_service = (
            latex_service if latex_service is not None else LatexRenderService(self)
        )
        self._latex_service.rendered.connect(self._on_latex_rendered)
        self._latex_service.failed.connect(self._on_latex_failed)
        self._latex_service.warning.connect(self._on_latex_warning)
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
        self._curves: list[Curve] = []
        self._series: tuple = ()
        self._plot_error = ""
        #: Incremented for every result; a scheduled plot from an older result
        #: must not replace the curves of a newer one.
        self._plot_token = 0
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

    def _clear_latex(self) -> None:
        """Empty the formula area's artwork."""
        self._latex_svg_url = ""
        self._latex_width = 0
        self._latex_height = 0

    def _request_result_latex(self) -> None:
        """Ask the renderer for the result's SVG, if there is one."""
        self._clear_latex()
        if not self._result_latex:
            return
        self._latex_seq += 1
        token = f"{self._latex_seq}:result"
        self._latex_pending[token] = ("result", -1)
        self._latex_service.request(token, self._result_latex, self._latex_style)

    def _refresh_strip(self) -> None:
        """Decide what the formula area holds, and request its artwork.

        The result's own LaTeX, or nothing at all: the area is the formula's alone,
        and the outcome line above carries whatever there is to *read* — a value, a
        failure, or the placeholder. (The empty state used to be typeset here, which
        turned a sentence into artwork and put the placeholder where the formula
        goes.)
        """
        self._request_result_latex()

    def _apply_variants(self, rows: Any) -> None:
        """Publish the alternative forms computed by the backend.

        The symbolic work (`doit`, `expand`, `factor`, `N`) already happened
        inside the backend's deadline. The rows are visible immediately; each
        row's artwork follows from the renderer.
        """
        self._variants = tuple(rows or ())
        self._render_variants()

    def _clear_variants(self) -> None:
        """Forget the alternative forms (a failure or a cleared result)."""
        self._variants = ()
        self._variant_items = []
        self.variantsChanged.emit()

    def _render_variants(self) -> None:
        """Build the card rows now and request their artwork in parallel."""
        items: list[dict] = []
        for variant in self._variants:
            items.append({
                "kind": variant.kind,
                "expression": variant.expression,
                "latex": variant.latex,
                "latexUrl": "",
                "naturalWidth": 0,
                "naturalHeight": 0,
            })
        self._variant_items = items
        self.variantsChanged.emit()
        for index, variant in enumerate(self._variants):
            if not variant.latex:
                continue
            self._latex_seq += 1
            token = f"{self._latex_seq}:variant:{index}"
            self._latex_pending[token] = ("variant", index)
            self._latex_service.request(token, variant.latex, self._latex_style)

    def _on_latex_rendered(
        self, token: str, url: str, width: int, height: int
    ) -> None:
        """Fill the result strip or one variant row when its SVG is ready."""
        target = self._latex_pending.pop(token, None)
        if target is None:
            return
        kind, index = target
        if kind == "result":
            self._latex_svg_url = url
            self._latex_width = width
            self._latex_height = height
            self.resultChanged.emit()
            return
        if 0 <= index < len(self._variant_items):
            row = self._variant_items[index]
            row["latexUrl"] = url
            row["naturalWidth"] = width
            row["naturalHeight"] = height
            self.variantsChanged.emit()

    def _on_latex_failed(self, token: str, message: str) -> None:
        """Log an unexpected renderer failure; the text surfaces still work."""
        if self._latex_pending.pop(token, None) is not None:
            self._log.add_warning(f"LaTeX render failed: {message}", "Calculator")

    def _on_latex_warning(self, message: str) -> None:
        """Write a renderer warning on the UI thread, where the log lives."""
        self._log.add_warning(message, "Calculator")

    def _get_variants(self) -> list[dict]:
        return self._variant_items

    def set_latex_style(self, style: LatexStyle) -> None:
        """Re-render the current result in a new style.

        One entry point for the three knobs: they all mean "draw it again", and
        they now arrive together — the theme owns the ink, the settings store the
        size and the font file, and `MainViewModel` assembles both into one
        `LatexStyle`. A new style invalidates every token; old renders may finish
        but cannot overwrite the new artwork.
        """
        if style == self._latex_style:
            return
        self._latex_style = style
        self._latex_service.begin_generation("calculator")
        self._latex_pending.clear()
        self._refresh_strip()
        self._render_variants()
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
    #: The result card's rows: {kind, expression, latex, latexUrl,
    #: naturalWidth, naturalHeight}. Empty on an error or a result with no
    #: alternative worth showing.
    variants = Property("QVariantList", _get_variants, notify=variantsChanged)

    def _get_backend_busy(self) -> bool:
        return self._backend_busy

    def _get_backend_status(self) -> str:
        """``ready`` | ``calculating`` | ``timedout`` | ``failed``."""
        return self._backend_status

    def _get_backend_timeout(self) -> float:
        return float(getattr(self._backend, "timeout_seconds", 0.0))

    backendBusy = Property(
        bool, _get_backend_busy, notify=backendStateChanged
    )
    backendStatus = Property(
        str, _get_backend_status, notify=backendStateChanged
    )
    #: Seconds a single request may run; 0 means the inline backend (no limit).
    backendTimeout = Property(
        float, _get_backend_timeout, constant=True
    )

    def _set_backend_state(self, busy: bool, status: str) -> None:
        """Publish one backend state transition."""
        if busy == self._backend_busy and status == self._backend_status:
            return
        self._backend_busy = busy
        self._backend_status = status
        self.backendStateChanged.emit()

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

    def _supported_series(self, series: tuple) -> tuple:
        """``series`` without the curves qmlmathplot's GLSL printer cannot spell.

        The plot is a *numeric* surface: a result that evaluates to a special
        function (`fresnels`, `gamma`, …) has no shader spelling. Dropping that
        one curve keeps the integrand/source curve useful and leaves the card
        without a printer stack trace; the evaluated form is still in the result
        card's `doit` row. `func_glsl` is the printer itself, so this asks the
        real capability rather than keeping a second whitelist.
        """
        supported = []
        for item in series:
            try:
                func_glsl(item.expression, "x")
            except Exception as exc:  # noqa: BLE001 - an unprintable curve is skipped
                reason = str(exc).splitlines()[0]
                self._log.add_info(f"Plot skipped: {reason}", "Calculator")
                continue
            supported.append(item)
        return tuple(supported)

    def _set_plot(self, series: tuple) -> None:
        """Reconcile the plot's curves with ``series``.

        Curves are reused slot by slot, so recalculating the same shape only
        changes the expressions — and qmlmathplot's bake cache makes that nearly
        free. A slot whose artist changes kind (explicit ↔ implicit) is rebuilt,
        because the two are different classes. Nothing here may raise: a plotting
        failure is a log line and the card's error text, not a broken Qt slot.
        """
        series = self._supported_series(series)
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
        self._backend.cancel()
        self._active_request = None
        self._pending = None
        self._last_completed_request = None
        self._latex_service.begin_generation("calculator")
        self._latex_pending.clear()
        self._plot_token += 1
        self._set_backend_state(False, "ready")
        self._result_text = ""
        self._result_latex = ""
        self._is_error = False
        self._error_message = ""
        self._clear_variants()
        self._set_plot(())
        self._refresh_strip()
        self.resultChanged.emit()

    def _apply_result(self, result: Result) -> None:
        """Apply a request's outcome, then schedule its plot separately."""
        # A new outcome invalidates every render from the previous one, even if
        # it is still in the renderer's queue.
        self._latex_service.begin_generation("calculator")
        self._latex_pending.clear()
        self._clear_variants()
        if isinstance(result, Success):
            self._result_text = str(result.value)
            self._result_latex = result.latex
            self._is_error = False
            self._error_message = ""
        else:
            self._result_text = ""
            self._result_latex = ""
            self._is_error = True
            self._error_message = self._format_failure(result)
        # Capture the generation before any notification: the renderer can
        # complete synchronously in headless mode, and a listener may start
        # another calculation, which must own the plot.
        self._plot_token += 1
        token = self._plot_token
        self._refresh_strip()
        self.resultChanged.emit()

        # Plot preparation is not part of the result. It stays on the UI thread
        # (qmlmathplot is Qt/GPU state) but runs after this notification.
        if QCoreApplication.instance() is None:
            self._apply_plot(result, token)
        else:
            QTimer.singleShot(0, lambda: self._apply_plot(result, token))

    def _apply_plot(self, result: Result, token: int) -> None:
        """Apply the curves for one result if it is still the current one."""
        if token != self._plot_token:
            return
        if isinstance(result, Success):
            self._set_plot(plot_series(result.value, result.origin))
        else:
            self._set_plot(())

    @staticmethod
    def _format_failure(failure: Failure) -> str:
        """User-facing error text: the message plus its hint, when there is one."""
        if failure.hint:
            return f"{failure.message} — {failure.hint}"
        return failure.message

    def _start_request(
        self,
        kind: str,
        payload: Any,
        pending: dict,
    ) -> None:
        """Hand one request to the backend, replacing any previous one.

        The id is allocated here, before submitting: a synchronous backend emits
        `finished` inside `submit`, and both backends then follow the same
        stale-reply path.
        """
        if self._active_request is not None:
            self._backend.cancel()
        # A variant message from the previous answer must not attach to the
        # result of this request, even if it arrives while this one is running.
        self._last_completed_request = None
        self._request_seq += 1
        self._active_request = self._request_seq
        self._pending = pending
        self._set_backend_state(True, "calculating")
        try:
            self._backend.submit(
                self._active_request,
                kind,
                payload,
                self._variable_manager.list_all(),
            )
        except Exception as exc:  # noqa: BLE001 - a broken boundary is reported
            self._on_backend_failed(
                self._active_request, f"{type(exc).__name__}: {exc}"
            )

    def _take_pending(self, request_id: int) -> dict | None:
        """Claim a reply, or return None when it belongs to a cancelled request."""
        if request_id != self._active_request:
            return None
        pending = self._pending
        self._pending = None
        self._active_request = None
        return pending

    def _on_backend_finished(self, request_id: int, result: Result) -> None:
        """A model answer arrived: display it, then record its effects."""
        pending = self._take_pending(request_id)
        if pending is None:
            return
        self._set_backend_state(False, "ready")
        # Identify the displayed result before notifying: a listener may start
        # another request, which must invalidate this one's late variants.
        self._last_completed_request = request_id
        # Result first: it no longer waits for optional variant rows.
        self._apply_result(result)
        if isinstance(result, Success):
            self._record_success(pending, result)
        else:
            self._record_failure(pending, result, allow_invalid=True)

    @Slot(int, object)
    def _on_variants_ready(self, request_id: int, rows: object) -> None:
        """Attach optional rows to the already displayed result, if it is current."""
        if request_id != self._last_completed_request:
            return
        if self._active_request is not None:
            return
        self._apply_variants(rows)

    def _on_backend_timed_out(self, request_id: int) -> None:
        """The backend killed a request at its deadline."""
        pending = self._take_pending(request_id)
        if pending is None:
            return
        self._set_backend_state(False, "timedout")
        timeout = self._get_backend_timeout()
        failure = Failure(
            pending["expression"],
            ErrorKind.TIMEOUT,
            f"Calculation timed out after {timeout:g} s.",
        )
        self._apply_result(failure)
        self._record_failure(pending, failure, allow_invalid=False)

    def _on_backend_failed(self, request_id: int, message: str) -> None:
        """The worker died or the boundary could not start/send."""
        pending = self._take_pending(request_id)
        if pending is None:
            return
        self._set_backend_state(False, "failed")
        failure = Failure(
            pending["expression"],
            ErrorKind.INTERNAL,
            f"Calculation backend failed: {message}",
        )
        self._apply_result(failure)
        self._record_failure(pending, failure, allow_invalid=False)

    def _record_success(self, pending: dict, result: Success) -> None:
        """History, log and variable-store effects of a successful request."""
        if pending["kind"] == "evaluate":
            self._history.add_item(
                pending["expression"], self._result_text, "Code",
                latex=result.latex,
            )
        else:
            self._history.add_item(
                pending["expression"],
                self._result_text,
                "Assign",
                latex=result.latex,
                name=pending["name"],
                op=pending["operator"],
            )
            self._save_variable(pending["name"], result.value)
        self._log.add_info(f"= {result.value}", "Calculator")

    def _record_failure(
        self,
        pending: dict,
        failure: Failure,
        allow_invalid: bool,
    ) -> None:
        """History and log effects of a failed request.

        ``allow_invalid`` is false for a timeout or backend crash: those say
        nothing about the value the user typed, so an Assign mode write must not
        be recorded as an invalid variable.
        """
        if pending["kind"] == "evaluate":
            # Failures are part of the history too: keeping the input and the
            # failure text is what lets a typo be sent back and fixed.
            self._history.add_item(
                pending["expression"], "", "Code",
                error=self._format_failure(failure),
            )
        else:
            self._history.add_item(
                pending["expression"],
                "",
                "Assign",
                name=pending["name"],
                op=pending["operator"],
                error=self._format_failure(failure),
            )
        self._log.add_error(f"Error: {failure.message}", "Calculator")

        if (pending["kind"] != "assign"
                or not allow_invalid
                or failure.kind is ErrorKind.INVALID_NAME
                or pending["operator"] != "="
                or self._variables_model is None):
            return
        try:
            self._variables_model.save_invalid(
                pending["name"], pending["expression"]
            )
        except Exception as exc:  # noqa: BLE001 - a store failure is a warning
            self._log.add_warning(
                f"Failed to store invalid entry: {exc}", "Calculator"
            )

    @Slot()
    def warmUpBackend(self) -> None:
        """Start the calculation and renderer processes after the first frame.

        The application calls this once after the first frame; the workers'
        imports then overlap window setup instead of the first Enter/result.
        """
        self._backend.warm_up()
        self._latex_service.warm_up()

    @Slot(str)
    def calculate(self, expression: str) -> None:
        """Submit an expression in code mode to the calculation backend."""
        self._log.add_info(expression, "Calculator")
        self._start_request(
            "evaluate",
            expression,
            {"kind": "evaluate", "expression": expression},
        )

    @Slot(str, str, str)
    def calculateAssign(self, name: str, operator: str, value_str: str) -> None:
        """Submit an assignment in assign mode to the calculation backend.

        The model still validates the target before evaluating anything, so a
        rejected write never reaches the history, the "= value" log line or the
        variable store. An unparsable value is still kept as an invalid (NaN)
        entry, so the user's input survives.
        """
        self._log.add_info(f"{name} {operator} {value_str}", "Calculator")
        self._start_request(
            "assign",
            Assignment(name, operator, value_str),
            {
                "kind": "assign",
                "expression": value_str,
                "name": name,
                "operator": operator,
            },
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
