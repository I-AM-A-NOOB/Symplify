"""Variables viewmodel for the QML Symplify app.

Exposes the VariableManager as a QAbstractTableModel so the shadow
TableView renders a real multi-column table, plus CRUD slots for the
page's toolbar. All mutations emit granular row signals (insert /
dataChanged / remove) so views update in place instead of resetting
wholesale.
"""

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import (
    Property,
    QAbstractEventDispatcher,
    QAbstractTableModel,
    QCoreApplication,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    Signal,
    Slot,
)

from ..latex_render import LatexStyle, render_data_url
from ..model import render_latex_definition
from ..model.calculator import (
    Assignment,
    Calculator,
    ErrorKind,
    Failure,
    Result,
)
from ..model.variable import VariableManager, reserved_name_warning
from .log_viewmodel import LogViewModel

if TYPE_CHECKING:
    from .search import VariablesFilterModel

#: Stop the dedicated Variables worker after this long without a write. The
#: next edit starts it again (SymPy import) and shows its result when ready;
#: keeping a third SymPy process alive while the page is idle cost ~140 MB.
BACKEND_IDLE_MS = 60_000


@dataclass(frozen=True)
class _WriteRequest:
    """One add/update waiting for the dedicated Variables worker."""

    request_id: int
    kind: str                 # "add" | "update"
    name: str
    text: str


class VariablesModel(QAbstractTableModel):
    """Table model of calculator variables.

    Columns: name / expression / type. The expression column shows the
    canonical sympy string for valid entries and the raw user input for
    invalid ones (whose value is NaN, which the type column labels "Invalid").

    In the application every write goes through a dedicated calculation
    ``backend``, so no expression is evaluated in the UI process and a runaway
    request is bounded by the backend's deadline. Requests are queued and sent
    one at a time: the worker answers one request, and a variable edit must not
    cancel the previous edit. With no backend (tests/headless) the same pipeline
    runs synchronously through the in-process ``Calculator`` and keeps the old
    return values.
    """

    warningOccurred = Signal(str, str)
    countChanged = Signal()
    #: Emitted after an add reaches the store (async or sync); QML selects it.
    variableAdded = Signal(str, bool)
    #: A queued write started or finished; the viewmodel restarts its idle stop.
    activity = Signal()

    def __init__(
        self,
        manager: VariableManager,
        log: LogViewModel | None = None,
        calculator: Calculator | None = None,
        backend: QObject | None = None,
        parent=None,
    ):
        """Initialize the variables model."""
        super().__init__(parent)
        self._manager = manager
        self._log = log
        self._backend = backend
        #: The in-process path is the headless/test fallback, never the app's.
        self._calculator = (
            None if backend is not None
            else calculator if calculator is not None else Calculator()
        )
        self._queue: deque[_WriteRequest] = deque()
        self._active: _WriteRequest | None = None
        self._request_seq = 0
        if backend is not None:
            backend.finished.connect(self._on_finished)
            backend.timedOut.connect(self._on_timed_out)
            backend.failed.connect(self._on_failed)
        #: Insertion-ordered variable names. Read off the manager rather than
        #: assumed empty: the app starts with the plotting variables in scope
        #: (``MainViewModel(initial_variables=…)``), and a table that began empty
        #: would show no rows until the first write.
        self._keys: list = manager.names()

    def roleNames(self):
        return {Qt.DisplayRole: b"display"}

    def flags(self, index: QModelIndex):
        """Name and expression columns are editable (Qt edit protocol)."""
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.isValid() and index.column() < 2:
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        """Handle inline edits from the TableView's edit delegate.

        Column 0 renames; column 1 re-parses the expression. An invalid
        expression is kept in the list as an invalid (NaN) entry so the
        user's input is never lost.
        """
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.EditRole):
            return False
        if index.column() >= 2:
            return False
        row = index.row()
        if row < 0 or row >= len(self._keys):
            return False
        name = self._keys[row]
        text = str(value)

        if index.column() == 0:
            if text == name:
                return True
            try:
                return self.rename(name, text)
            except ValueError as e:
                #: The write is refused, so the view keeps the editor open and
                #: nothing moves. Silence is what made that read as "the table
                #: ignored my Return": the first Enter *did* run, and this is the
                #: only thing it could do. The dialog names the reason, and the
                #: editor keeps the text so it can be corrected where it was typed.
                self._log_error(f"Failed to rename variable: {e}")
                self.warningOccurred.emit(text, str(e))
                return False

        return self.update(name, text)

    def _log_info(self, message: str) -> None:
        if self._log is not None:
            self._log.add_info(message, "Variables")

    def _log_warn(self, message: str) -> None:
        if self._log is not None:
            self._log.add_warning(message, "Variables")

    def _log_error(self, message: str) -> None:
        if self._log is not None:
            self._log.add_error(message, "Variables")

    def _assign_direct(self, name: str, value_str: str) -> Result:
        """Evaluate a write in-process; only the headless/test path reaches it."""
        assert self._calculator is not None
        return self._calculator.assign(
            Assignment(name, "=", value_str), self._manager.list_all()
        )

    def pending_add_names(self) -> set[str]:
        """Add names already queued or running, so the next name skips them."""
        names = {request.name for request in self._queue if request.kind == "add"}
        if self._active is not None and self._active.kind == "add":
            names.add(self._active.name)
        return names

    def _enqueue(self, kind: str, name: str, value_str: str) -> None:
        self._request_seq += 1
        self._queue.append(_WriteRequest(self._request_seq, kind, name, value_str))
        self.activity.emit()
        self._start_next()

    def is_idle(self) -> bool:
        """True when no write is queued or running (the worker may be stopped)."""
        return self._active is None and not self._queue

    def _start_next(self) -> None:
        """Send the oldest queued request; one worker request at a time."""
        if self._backend is None or self._active is not None or not self._queue:
            return
        request = self._queue.popleft()
        self._active = request
        try:
            self._backend.submit(
                request.request_id,
                "variable",
                Assignment(request.name, "=", request.text),
                self._manager.list_all(),
            )
        except Exception as exc:  # noqa: BLE001 - start failure is a write failure
            self._finish(
                request.request_id,
                Failure(
                    request.text,
                    ErrorKind.INTERNAL,
                    f"{type(exc).__name__}: {exc}",
                ),
                transport_error=True,
            )

    def _on_finished(self, request_id: int, result: Result) -> None:
        self._finish(request_id, result)

    def _on_timed_out(self, request_id: int) -> None:
        self._finish(
            request_id,
            Failure("", ErrorKind.TIMEOUT, "Variable request timed out."),
            transport_error=True,
        )

    def _on_failed(self, request_id: int, message: str) -> None:
        self._finish(
            request_id,
            Failure("", ErrorKind.INTERNAL, f"Calculation backend failed: {message}"),
            transport_error=True,
        )

    def _finish(
        self, request_id: int, result: Result, *, transport_error: bool = False
    ) -> None:
        """Apply one backend answer and send the next queued write.

        A transport error (timeout/crash/start failure) is not a statement about
        the expression: an existing variable keeps its old value and only the
        log says the update did not complete.
        """
        if self._active is None or self._active.request_id != request_id:
            return
        request = self._active
        self._active = None
        if request.kind == "add":
            self._apply_add(request.name, request.text, result)
        else:
            self._apply_update(
                request.name, request.text, result,
                preserve_on_error=transport_error,
            )
        self.activity.emit()
        self._start_next()

    def add(self, name: str, value_str: str) -> bool:
        """Add one variable; async backends answer through ``variableAdded``."""
        if self._backend is not None:
            self._enqueue("add", name, value_str)
            return True
        return self._apply_add(name, value_str, self._assign_direct(name, value_str))

    def _apply_add(self, name: str, value_str: str, result: Result) -> bool:
        if isinstance(result, Failure):
            self._log_error(f"Failed to add variable: {result.message}")
            self.variableAdded.emit(name, False)
            return False
        self.save(name, result.value)
        self._log_info(f"Variable added: {name} = {result.value}")
        self._warn_reserved(name)
        self.variableAdded.emit(name, True)
        return True

    def update(self, name: str, value_str: str) -> bool:
        """Re-parse one variable's value; an unparsable entry is kept as invalid.

        One route for the inline cell editor and the page's fields, so the two
        cannot disagree about what "kept as invalid" means (the user's input is
        never lost) or about which failures are refusals instead. With an async
        backend the same decision lands when the result arrives; the return value
        then only says the request was accepted.
        """
        if not self._manager.exists(name):
            self._log_error(f"Variable '{name}' does not exist")
            return False
        if self._backend is not None:
            self._enqueue("update", name, value_str)
            return True
        try:
            result = self._assign_direct(name, value_str)
        except Exception as parse_err:  # noqa: BLE001 - kept, never lost
            self.save_invalid(name, value_str)
            self._log_warn(f"Variable '{name}' kept as invalid: {parse_err}")
            return True
        return self._apply_update(name, value_str, result)

    def _apply_update(
        self, name: str, value_str: str, result: Result,
        *, preserve_on_error: bool = False,
    ) -> bool:
        if not self._manager.exists(name):
            # Renamed or deleted while the request was in flight: the old target
            # must not be re-created by a late answer.
            return False
        if isinstance(result, Failure):
            if result.kind is ErrorKind.INVALID_NAME:
                self._log_error(f"Failed to update variable: {result.message}")
                return False
            if preserve_on_error:
                self._log_warn(
                    f"Variable '{name}' update did not complete: {result.message}; "
                    "kept the previous value"
                )
                return False
            self.save_invalid(name, value_str)
            self._log_warn(f"Variable '{name}' kept as invalid: {result.message}")
            return True
        self.save(name, result.value)
        self._log_info(f"Variable updated: {name} = {result.value}")
        self._warn_reserved(name)
        return True

    def _warn_reserved(self, name: str) -> None:
        """Emit the warning for a name input's meaning depends on.

        A SymPy built-in changes what an expression resolves to; a plotting
        variable changes what the plot reads. Both are stored anyway — the
        warning is the whole of the consequence, as it always was for built-ins.
        """
        warning = reserved_name_warning(name)
        if warning is None:
            return
        self.warningOccurred.emit(name, warning)
        self._log_warn(warning)

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of variables."""
        return 0 if parent.isValid() else len(self._keys)

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the fixed column count (name, expression, type)."""
        return 0 if parent.isValid() else 3

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._keys):
            return None
        entry = self._manager.entry(self._keys[row])
        if entry is None:
            return None
        if role == Qt.DisplayRole:
            return (entry.name, entry.expr_str, entry.type_label)[index.column()]
        return None

    def _after_mutation(self, name: str, is_new: bool) -> None:
        """Emit the granular signal for an upsert of ``name``."""
        if is_new:
            row = len(self._keys)
            self.beginInsertRows(QModelIndex(), row, row)
            self._keys.append(name)
            self.endInsertRows()
            self.countChanged.emit()
        else:
            row = self._keys.index(name)
            self.dataChanged.emit(
                self.index(row, 0), self.index(row, self.columnCount() - 1)
            )

    def save(self, name: str, value: Any) -> None:
        """Insert or update a valid entry, notifying granularly."""
        is_new = not self._manager.exists(name)
        self._manager.save(name, value)
        self._after_mutation(name, is_new)

    def save_invalid(self, name: str, raw_expr: str) -> None:
        """Insert or update an invalid (NaN) entry, notifying granularly."""
        is_new = not self._manager.exists(name)
        self._manager.save_invalid(name, raw_expr)
        self._after_mutation(name, is_new)

    def rename(self, old_name: str, new_name: str) -> bool:
        """Rename via the manager, notifying granularly."""
        if old_name not in self._keys:
            return False
        if not self._manager.rename(old_name, new_name):
            return False
        row = self._keys.index(old_name)
        self._keys[row] = new_name
        self.dataChanged.emit(
            self.index(row, 0), self.index(row, self.columnCount() - 1)
        )
        self._log_info(f"Variable renamed: {old_name} -> {new_name}")
        # Both ends matter: renaming x away takes the plotting name with it,
        # renaming something *to* x replaces the variable.
        self._warn_reserved(old_name)
        self._warn_reserved(new_name)
        return True

    def remove(self, name: str) -> bool:
        """Remove an entry, notifying granularly. Returns True if removed."""
        if name not in self._keys:
            return False
        row = self._keys.index(name)
        self.beginRemoveRows(QModelIndex(), row, row)
        self._manager.delete(name)
        self._keys.pop(row)
        self.endRemoveRows()
        self.countChanged.emit()
        self._log_info(f"Variable deleted: {name}")
        # Deleting is a modification too: a plotting variable that is gone is
        # exactly what the next plot cannot read.
        self._warn_reserved(name)
        return True

    @Slot(int, int, result=str)
    def cellAt(self, row: int, column: int) -> str:
        """Return the cell text at (row, column), callable from QML."""
        if 0 <= row < len(self._keys) and 0 <= column < 3:
            entry = self._manager.entry(self._keys[row])
            if entry:
                return (entry.name, entry.expr_str, entry.type_label)[column]
        return ""

    @Slot(int, result=str)
    def latexAt(self, row: int) -> str:
        """Return ``name = expression`` for the row as one LaTeX line ("" when none).

        The whole definition, not just the value: sympy typesets the *name* too, so
        ``alpha`` and its Greek expression have to be rendered together or the two
        halves read as different variables. An invalid entry, or a value sympy
        cannot render, answers "" — the caller's cue to show the raw entry instead.
        """
        if 0 <= row < len(self._keys):
            entry = self._manager.entry(self._keys[row])
            if entry is not None and entry.valid:
                return render_latex_definition(entry.name, entry.obj)
        return ""

    @Slot(int, result=str)
    def nameAt(self, row: int) -> str:
        """Return the variable name at ``row`` (or empty string)."""
        return self.cellAt(row, 0)

    def _get_count(self) -> int:
        """Number of rows."""
        return len(self._keys)

    count = Property(int, _get_count, notify=countChanged)


class VariablesViewModel(QObject):
    """Connects the VariableManager model to the QML variables page.

    Signals:
        warningOccurred: Emitted when the user touches a name input's meaning
            depends on — a SymPy built-in or a plotting variable.
            Args: title (str), content (str).
    """

    warningOccurred = Signal(str, str)
    #: An add reached the store (or failed); the page selects the new row.
    variableAdded = Signal(str, bool)
    #: The rendering style changed: the details panel must ask for new artwork.
    latexStyleChanged = Signal()

    def __init__(
        self,
        variable_manager: VariableManager,
        log: LogViewModel,
        calculator: Calculator | None = None,
        backend: QObject | None = None,
        parent: QObject | None = None,
    ):
        """Initialize the variables viewmodel.

        ``backend`` is the application's dedicated Variables worker. With no
        backend (tests/headless) writes run through ``calculator`` in-process.
        """
        super().__init__(parent)
        self._variable_manager = variable_manager
        self._log = log
        self._backend = backend
        self._calculator = calculator if calculator is not None else Calculator()
        self._filter = None
        self._latex_style = LatexStyle()
        #: ``(latex, style) -> {url, width, height}`` for the details panel. The
        #: page calls `latexFor` from a binding forced by `dataRevision`; a row
        #: that did not change re-asks for the same artwork, and a ziamath render
        #: is ~7 ms. Small and bounded: one selected row at a time.
        self._preview_cache: dict[tuple[str, LatexStyle], dict] = {}
        self._model = VariablesModel(
            variable_manager, log, self._calculator, backend=backend, parent=self
        )
        self._model.warningOccurred.connect(self.warningOccurred)
        self._model.variableAdded.connect(self.variableAdded)
        self._model.activity.connect(self._touch_backend)
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(BACKEND_IDLE_MS)
        self._idle_timer.timeout.connect(self._stop_idle_backend)

    def _get_model(self) -> VariablesModel:
        return self._model

    model = Property(QObject, _get_model, constant=True)

    def attach_filter(self, filter_model: "VariablesFilterModel") -> None:
        """Point the page's row lookups at the search proxy.

        The details panel addresses rows as the *proxy* shows them, so the
        viewmodel needs the same mapping the page's table uses.
        """
        self._filter = filter_model

    def set_latex_style(self, style: LatexStyle) -> None:
        """Take a new rendering style and tell the page it has to ask again."""
        if style == self._latex_style:
            return
        self._latex_style = style
        self._preview_cache.clear()
        self.latexStyleChanged.emit()

    @Slot(int, result=str)
    def latexAt(self, row: int) -> str:
        """The visible row's expression as LaTeX ("" when it has none)."""
        if self._filter is None:
            return ""
        return self._filter.latexAt(row)

    @Slot(int, result="QVariantMap")
    def latexFor(self, row: int) -> dict:
        """``{url, width, height}`` for the visible row's definition.

        Rendered on demand, memoized by the definition text and the style: the
        page re-asks whenever the selection or the model changes, and a row that
        did not change would otherwise pay for the same ziamath layout again.
        """
        latex = self.latexAt(row)
        key = (latex, self._latex_style)
        cached = self._preview_cache.get(key)
        if cached is not None:
            return cached
        url, width, height = render_data_url(latex, self._latex_style)
        result = {"url": url, "width": width, "height": height}
        if len(self._preview_cache) >= 32:
            self._preview_cache.clear()
        self._preview_cache[key] = result
        return result

    @Slot(str, str, result=bool)
    def addVariable(self, name: str, value_str: str) -> bool:
        """Add a variable through the model's shared write pipeline."""
        return self._model.add(name, value_str)

    @Slot(str, result=bool)
    def deleteVariable(self, name: str) -> bool:
        """Delete a variable (the model owns the log line and the warning)."""
        return self._model.remove(name)

    @Slot(str, str, result=bool)
    def renameVariable(self, old_name: str, new_name: str) -> bool:
        """Rename a variable; a refused name is logged and answered False."""
        try:
            return self._model.rename(old_name, new_name)
        except ValueError as exc:
            self._log.add_error(f"Failed to rename variable: {exc}", "Variables")
            return False

    @Slot(str, str, result=bool)
    def updateVariable(self, name: str, value_str: str) -> bool:
        """Update a variable's value through the model's shared pipeline."""
        return self._model.update(name, value_str)

    @Slot(result=str)
    def generateUniqueName(self) -> str:
        """Generate a default name that also skips queued adds.

        Two quick `+` clicks would otherwise both ask the manager for `var_1`:
        the first add has not reached the manager yet, so it cannot reserve the
        name.
        """
        pending = self._model.pending_add_names()
        counter = 1
        while True:
            name = f"var_{counter}"
            if (name not in pending
                    and not self._variable_manager.exists(name)
                    and self._variable_manager.validate_name(name)):
                return name
            counter += 1

    @Slot()
    def warmUpBackend(self) -> None:
        """Start the Variables worker after the first frame, hiding SymPy's import."""
        if self._backend is not None:
            self._backend.warm_up()
            self._touch_backend()

    def _touch_backend(self) -> None:
        if self._backend is None:
            return
        # A QCoreApplication can outlive its dispatcher during teardown; a timer
        # started then would only print "event dispatcher destroyed".
        if (QCoreApplication.instance() is not None
                and QAbstractEventDispatcher.instance() is not None
                and not QCoreApplication.closingDown()):
            self._idle_timer.start()

    @Slot()
    def stopBackendIfIdle(self) -> None:
        """Reclaim the Variables worker when the page is idle or being left."""
        self._stop_idle_backend()

    def _stop_idle_backend(self) -> None:
        if self._backend is None:
            return
        if self._model.is_idle():
            self._backend.shutdown()
            self._idle_timer.stop()
        else:
            # A write is still queued/running; check again after another window.
            self._touch_backend()
