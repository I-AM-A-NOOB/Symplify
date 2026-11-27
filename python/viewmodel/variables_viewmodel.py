"""Variables viewmodel for the QML Symplify app.

Exposes the VariableManager as a QAbstractTableModel so the shadow
TableView renders a real multi-column table, plus CRUD slots for the
page's toolbar. All mutations emit granular row signals (insert /
dataChanged / remove) so views update in place instead of resetting
wholesale.
"""

from collections import deque
from dataclasses import dataclass, replace
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
from ..store_client import StoreClient, StoreClientError
from ..worker_protocol import (
    Assignment,
    CommitRequest,
    ErrorKind,
    ParsePolicy,
    ResultView,
    ScopeChange,
    ScopeDelta,
    ScopeSnapshot,
    StoreEntry,
    StoreEntryCandidate,
    StoreReply,
)
from .log_viewmodel import LogViewModel
from .warnings import localize_warning

if TYPE_CHECKING:
    from .search import VariablesFilterModel

#: Stop the dedicated Variables worker after this long without a write. The
#: next edit starts it again (SymPy import) and shows its result when ready;
#: keeping a third SymPy process alive while the page is idle cost ~140 MB.
BACKEND_IDLE_MS = 60_000

#: How many recent Store deltas the model keeps for computing a request's
#: scope. If the sender is older than this, the next request gets a snapshot.
MAX_SCOPE_HISTORY = 256

#: A worker that could not apply the scope says so as an INTERNAL failure. These
#: are not expression failures: the worker's cache is out of step, and the write
#: is retried once with a full snapshot instead of failing the user's edit.
_SCOPE_ERRORS = ("ScopeConflictError", "ScopeGapError", "ScopeStaleError")


@dataclass(frozen=True)
class _WriteRequest:
    """One add/update waiting for the dedicated Variables worker."""

    request_id: int
    kind: str                 # "add" | "update"
    name: str
    text: str
    #: A scope-sync failure is retried once with a full snapshot. The same
    #: request id keeps the pending draft, so the table does not flicker.
    retried: bool = False


@dataclass(frozen=True)
class _PendingDraft:
    """The latest text the table shows while its worker request is in flight."""

    request_id: int
    text: str


def _is_legacy_failure(result: Any) -> bool:
    """True for the test-only ``Failure`` (lazy: never imports SymPy in the app)."""
    from ..model.calculator import Failure

    return isinstance(result, Failure)


class VariablesModel(QAbstractTableModel):
    """Table model of calculator variables.

    Columns: name / expression / type. The expression column shows the
    Store's display string for valid entries and the raw user input for invalid
    ones (whose type column says "Invalid").

    In the application ``store`` is the Store worker client: rows are
    ``StoreEntry`` strings, writes evaluate through the dedicated ``backend`` and
    commit a ``StoreEntryCandidate``. With no store (tests/headless) the same
    pipeline runs over ``VariableManager`` and the in-process ``Calculator``.
    Requests are queued and sent one at a time: a variable edit must not cancel
    the previous edit.
    """

    warningOccurred = Signal(str, str)
    countChanged = Signal()
    #: Emitted after an add reaches the store (async or sync); QML selects it.
    variableAdded = Signal(str, bool)
    #: A queued write started or finished; the viewmodel restarts its idle stop.
    activity = Signal()
    #: A row's draft appeared or was committed; QML re-reads the expression cell.
    pendingChanged = Signal()
    #: The worker queue became busy or idle; the page's spinner/abort follows it.
    busyChanged = Signal()

    def __init__(
        self,
        manager: Any | None,
        log: LogViewModel | None = None,
        calculator: Any | None = None,
        backend: QObject | None = None,
        store: StoreClient | None = None,
        parent=None,
    ):
        """Initialize the variables model.

        ``store`` is the application's Store worker client: the table then reads
        ``StoreEntry`` strings and every write is a ``CommitRequest``. Without
        it, the model keeps the legacy ``VariableManager`` path used by the
        headless tests and the in-process backend.
        """
        super().__init__(parent)
        self._manager = manager
        self._log = log
        self._backend = backend
        self._store = store
        if store is not None and backend is None:
            raise ValueError("store-backed variables need a write backend")
        self._revision = 0
        self._entries: dict[str, StoreEntry] = {}
        #: The in-process path is the headless/test fallback, never the app's.
        if backend is not None or store is not None:
            self._calculator = None
        elif calculator is not None:
            self._calculator = calculator
        else:
            from ..model.calculator import Calculator

            self._calculator = Calculator()
        self._queue: deque[_WriteRequest] = deque()
        self._active: _WriteRequest | None = None
        self._request_seq = 0
        self._pending: dict[str, _PendingDraft] = {}
        #: Recent Store deltas, so the next Compute request can send only what
        #: changed since the last revision it confirmed.
        self._scope_history: list[ScopeDelta] = []
        self._last_scope_generation: int | None = None
        #: The Variables worker has its own scope cache; keep its generation and
        #: last sent revision separate from the Calculator worker's.
        self._write_scope_generation: int | None = None
        self._write_scope_revision: int | None = None
        self._parse_policy = ParsePolicy()
        if backend is not None:
            backend.finished.connect(self._on_finished)
            backend.timedOut.connect(self._on_timed_out)
            backend.failed.connect(self._on_failed)
            backend.cancelled.connect(self._on_cancelled)
        if store is not None:
            snapshot = store.snapshot()
            self._revision = snapshot.revision
            self._entries = {entry.name: entry for entry in snapshot.entries}
            self._keys: list[str] = list(self._entries)
        else:
            if manager is None:
                raise ValueError("VariablesModel needs a manager or a store client")
            #: Insertion-ordered variable names. Read off the manager rather than
            #: assumed empty: the legacy/headless path may start with explicit
            #: ``initial_variables``, and a table that ignored them would show no
            #: rows until the first write. The application's Store starts empty.
            self._keys = manager.names()

    def is_store_backed(self) -> bool:
        """True when the table is fed by the Store worker (the application)."""
        return self._store is not None

    def names(self) -> tuple[str, ...]:
        return tuple(self._keys)

    def entries(self) -> tuple[StoreEntry, ...]:
        """Every committed Store entry in table order (store mode only)."""
        return tuple(self._entries.values())

    def scope_snapshot(self):
        """The scope to send with a Compute request (strongly revisioned)."""
        if self._store is not None:
            # The model already mirrors every committed entry and revision; a
            # fresh store.snapshot() would be a blocking IPC on the UI thread.
            return ScopeSnapshot(self._revision, self.entries())
        return self._manager.list_all()

    def scope_for(self, generation: int, sent_revision: int | None):
        """The smallest scope that brings ``generation`` up to date.

        A new worker (or no known revision) gets a snapshot; otherwise the
        recent Store deltas are merged into one delta. If the sender is older
        than the retained history, fall back to a snapshot rather than guess.
        """
        if self._store is None:
            return self._manager.list_all()
        if generation != self._last_scope_generation or sent_revision is None:
            self._last_scope_generation = generation
            return self.scope_snapshot()
        return self._scope_since(sent_revision)

    def _scope_since(self, sent_revision: int):
        """The smallest Store scope after ``sent_revision``, or a snapshot."""
        if sent_revision > self._revision:
            return self.scope_snapshot()
        if sent_revision == self._revision:
            return ScopeDelta(self._revision, self._revision, ())
        history = [d for d in self._scope_history if d.revision > sent_revision]
        if not history or history[0].base_revision > sent_revision:
            return self.scope_snapshot()
        latest: dict[str, ScopeChange] = {}
        for delta in history:
            for change in delta.changes:
                latest[change.name] = change
        return ScopeDelta(sent_revision, self._revision, tuple(latest.values()))

    def _scope_for_write(self):
        """The Variables worker's scope, reusing deltas between writes.

        The write worker is a separate process with its own scope cache. It
        starts with a snapshot; after that, only the Store changes since the
        revision it was sent are transmitted. A worker replacement (idle stop,
        timeout, crash) gets a fresh snapshot.
        """
        if self._store is None:
            return self.scope_snapshot()
        generation = int(getattr(self._backend, "generation", 0))
        if (generation != self._write_scope_generation
                or self._write_scope_revision is None):
            self._write_scope_generation = generation
            self._write_scope_revision = self._revision
            return self.scope_snapshot()
        return self._scope_since(self._write_scope_revision)

    def set_parse_policy(self, policy: ParsePolicy) -> None:
        """Use ``policy`` for subsequent Variables-worker writes."""
        if not isinstance(policy, ParsePolicy):
            raise TypeError(
                f"parse_policy must be ParsePolicy, got {type(policy).__name__}"
            )
        self._parse_policy = policy
        if self._calculator is not None:
            self._calculator.set_parse_policy(policy)

    def _remember_scope_delta(self, delta: ScopeDelta | None) -> None:
        if delta is None:
            return
        self._scope_history.append(delta)
        if len(self._scope_history) > MAX_SCOPE_HISTORY:
            del self._scope_history[:-MAX_SCOPE_HISTORY]

    def _entry(self, name: str):
        """The committed entry, whichever backend owns it."""
        if self._store is not None:
            return self._entries.get(name)
        return self._manager.entry(name)

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

    def _assign_direct(self, name: str, value_str: str) -> Any:
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
        request = _WriteRequest(self._request_seq, kind, name, value_str)
        # A newer edit of the same name supersedes stale queued writes. The
        # active one cannot be recalled, but `_finish` ignores its answer once
        # this newer draft is pending.
        self._queue = deque(item for item in self._queue if item.name != name)
        self._queue.append(request)
        self._pending[name] = _PendingDraft(request.request_id, value_str)
        self._notify_row(name)
        self.pendingChanged.emit()
        self.busyChanged.emit()
        self.activity.emit()
        self._start_next()

    def is_busy(self) -> bool:
        """True while a worker request is running or queued (spinner/abort)."""
        return self._active is not None or bool(self._queue)

    def is_pending(self, name: str) -> bool:
        """True while ``name`` has a draft the page should mark as calculating."""
        return name in self._pending

    def cancel_active(self) -> bool:
        """Abort the running request; its raw draft is kept as Invalid.

        Only the active request is cancelled. Queued writes for the same name are
        dropped so a later answer cannot overwrite the preserved raw text; other
        names keep their place in the queue.
        """
        if self._backend is None or self._active is None:
            return False
        self._backend.cancel(notify=True)
        return True

    def _clear_pending(self, name: str) -> None:
        """Drop a draft and make the table re-read its committed value."""
        if self._pending.pop(name, None) is None:
            return
        self._notify_row(name)
        self.pendingChanged.emit()

    def _notify_row(self, name: str) -> None:
        """Re-read one row if it still exists."""
        if name not in self._keys:
            return
        row = self._keys.index(name)
        self.dataChanged.emit(
            self.index(row, 0), self.index(row, self.columnCount() - 1)
        )

    def is_idle(self) -> bool:
        """True when no write is queued or running (the worker may be stopped)."""
        return self._active is None and not self._queue

    def _start_next(self) -> None:
        """Send the oldest queued request; one worker request at a time."""
        if self._backend is None or self._active is not None or not self._queue:
            return
        request = self._queue.popleft()
        self._active = request
        scope = self._scope_for_write()
        sent_revision = getattr(scope, "revision", self._revision)
        # Publish it before `submit`: a synchronous backend can answer and start
        # the next queued write before this call returns.
        self._write_scope_revision = sent_revision
        try:
            set_policy = getattr(self._backend, "set_parse_policy", None)
            if set_policy is not None:
                set_policy(self._parse_policy)
            self._backend.submit(
                request.request_id,
                "variable",
                Assignment(request.name, "=", request.text),
                scope,
            )
        except Exception as exc:  # noqa: BLE001 - start failure is a write failure
            # The worker may have been replaced or never received the scope.
            self._write_scope_revision = None
            self._finish(
                request.request_id,
                ResultView(
                    request_id=request.request_id,
                    expression=request.text,
                    text="",
                    latex="",
                    is_error=True,
                    error_message=f"{type(exc).__name__}: {exc}",
                    hint="",
                    variants=(),
                    plot=(),
                    scope_revision=0,
                    profile_id="default",
                    error_kind="INTERNAL",
                ),
                transport_error=True,
            )

    def _on_finished(self, request_id: int, result: Any) -> None:
        self._finish(request_id, result)

    def _on_timed_out(self, request_id: int) -> None:
        self._finish(
            request_id,
            ResultView(
                request_id=request_id,
                expression="",
                text="",
                latex="",
                is_error=True,
                error_message="Variable request timed out.",
                hint="",
                variants=(),
                plot=(),
                scope_revision=0,
                profile_id="default",
                error_kind="TIMEOUT",
            ),
            transport_error=True,
        )

    def _on_failed(self, request_id: int, message: str) -> None:
        self._finish(
            request_id,
            ResultView(
                request_id=request_id,
                expression="",
                text="",
                latex="",
                is_error=True,
                error_message=f"Calculation backend failed: {message}",
                hint="",
                variants=(),
                plot=(),
                scope_revision=0,
                profile_id="default",
                error_kind="INTERNAL",
            ),
            transport_error=True,
        )

    def _on_cancelled(self, request_id: int) -> None:
        """Aborting a request keeps its latest raw draft, as Invalid.

        The old value is deliberately not restored: the user asked to stop the
        slow work, not to discard what was typed. A queued edit of the same name
        is dropped; otherwise it would run next and overwrite this raw draft.
        """
        if self._active is None or self._active.request_id != request_id:
            return
        request = self._active
        self._active = None
        # The abort may have reached the worker before it applied the scope.
        self._write_scope_revision = None
        self._write_scope_generation = None
        pending = self._pending.get(request.name)
        text = pending.text if pending is not None else request.text
        self._clear_pending(request.name)
        self._queue = deque(
            item for item in self._queue if item.name != request.name
        )
        if request.kind == "add" or (
            request.name in self._entries
            if self._store is not None
            else self._manager.exists(request.name)
        ):
            if self._store is not None:
                self._commit_invalid(request.name, text)
            else:
                self.save_invalid(request.name, text)
            self._log_warn(
                f"Variable '{request.name}' calculation aborted: "
                "kept the input as invalid"
            )
            if request.kind == "add":
                self.variableAdded.emit(request.name, False)
        self.busyChanged.emit()
        self.activity.emit()
        self._start_next()

    def _finish(
        self, request_id: int, result: Any, *, transport_error: bool = False
    ) -> None:
        """Apply one backend answer and send the next queued write.

        A transport error (timeout/crash/start failure) is not a statement about
        the expression: an existing variable keeps its old value and only the
        log says the update did not complete. An explicit abort is different:
        `_on_cancelled` keeps the typed draft as Invalid.
        """
        if self._active is None or self._active.request_id != request_id:
            return
        request = self._active
        self._active = None
        pending = self._pending.get(request.name)
        if pending is not None and pending.request_id != request_id:
            # A newer edit of the same name is pending; this answer is stale.
            # Keep the newer draft and let its request run next.
            self.busyChanged.emit()
            self.activity.emit()
            self._start_next()
            return

        message = getattr(result, "error_message", "")
        scope_error = isinstance(message, str) and message.startswith(_SCOPE_ERRORS)
        if transport_error or scope_error:
            # The worker may not have applied the scope it was sent, so its
            # revision cannot be trusted; the next request starts from a
            # snapshot. This is the same reset the Calculator path does on any
            # error, and it stops one bad delta from cascading.
            self._write_scope_revision = None
            self._write_scope_generation = None
        if scope_error and not request.retried:
            # The edit itself is fine — the worker's scope cache was out of
            # step. Keep the draft and retry once with a full snapshot.
            self._queue.appendleft(replace(request, retried=True))
            self._log_info(f"Variable scope resynced; retrying '{request.name}'")
            self.busyChanged.emit()
            self.activity.emit()
            self._start_next()
            return

        self._clear_pending(request.name)
        if request.kind == "add":
            self._apply_add(request.name, request.text, result)
        else:
            self._apply_update(
                request.name, request.text, result,
                preserve_on_error=transport_error,
            )
        self.busyChanged.emit()
        self.activity.emit()
        self._start_next()

    def add(self, name: str, value_str: str) -> bool:
        """Add one variable; async backends answer through ``variableAdded``."""
        if self._backend is not None:
            self._enqueue("add", name, value_str)
            return True
        return self._apply_add(name, value_str, self._assign_direct(name, value_str))

    def _apply_add(self, name: str, value_str: str, result: Any) -> bool:
        if self._store is not None:
            return self._apply_store_write(
                "add", name, value_str, result, preserve_on_error=False)
        if isinstance(result, ResultView):
            self._log_error("The calculation backend returned no SymPy value")
            self.variableAdded.emit(name, False)
            return False
        if _is_legacy_failure(result):
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
        if self._store is not None:
            if name not in self._keys:
                self._log_error(f"Variable '{name}' does not exist")
                return False
        elif not self._manager.exists(name):
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
        self, name: str, value_str: str, result: Any,
        *, preserve_on_error: bool = False,
    ) -> bool:
        if self._store is not None:
            if name not in self._keys:
                return False
            return self._apply_store_write(
                "update", name, value_str, result,
                preserve_on_error=preserve_on_error,
            )
        if isinstance(result, ResultView):
            self._log_error("The calculation backend returned no SymPy value")
            return False
        if not self._manager.exists(name):
            # Renamed or deleted while the request was in flight: the old target
            # must not be re-created by a late answer.
            return False
        if _is_legacy_failure(result):
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

    # --- Store-backed writes ---------------------------------------------

    def _apply_store_write(
        self,
        kind: str,
        name: str,
        raw: str,
        result: Any,
        *,
        preserve_on_error: bool,
    ) -> bool:
        """Apply one Compute answer through the Store, without SymPy."""
        if isinstance(result, ResultView):
            is_error = result.is_error
            error_kind = result.error_kind
            message = result.error_message
        else:
            is_error = _is_legacy_failure(result)
            error_kind = result.kind.name if is_error else ""
            message = result.message if is_error else ""
        if is_error:
            if error_kind == "INVALID_NAME":
                self._log_error(f"Failed to {kind} variable: {message}")
                if kind == "add":
                    self.variableAdded.emit(name, False)
                return False
            if preserve_on_error:
                self._log_warn(
                    f"Variable '{name}' update did not complete: {message}; "
                    "kept the previous value"
                )
                return False
            if kind == "add":
                # A failed add creates no row, matching the legacy path.
                self._log_error(f"Failed to add variable: {message}")
                self.variableAdded.emit(name, False)
                return False
            if not self._commit_invalid(name, raw):
                return False
            self._log_warn(f"Variable '{name}' kept as invalid: {message}")
            return True

        candidate = getattr(result, "entry", None)
        if candidate is None and not isinstance(result, ResultView):
            from ..result_payload import assignment_candidate

            candidate = assignment_candidate(name, result.value)
        if candidate is None:
            self._log_error("The calculation backend returned no variable entry")
            if kind == "add":
                self.variableAdded.emit(name, False)
            return False
        if not self._commit_entry(candidate):
            if kind == "add":
                self.variableAdded.emit(name, False)
            return False
        if kind == "add":
            self._log_info(f"Variable added: {candidate.name} = {candidate.display}")
            self.variableAdded.emit(candidate.name, True)
        else:
            self._log_info(f"Variable updated: {candidate.name} = {candidate.display}")
        self._emit_warning(candidate)
        return True

    def commit_candidate(self, candidate: StoreEntryCandidate) -> bool:
        """Commit a Compute candidate (Calculator's Assign path).

        The caller owns the warning: it has the candidate and can emit once,
        whereas this model's own write pipeline emits its own.
        """
        if self._store is None:
            return False
        return self._commit_entry(candidate)

    def _commit_invalid(self, name: str, raw: str) -> bool:
        return self._commit_entry(
            StoreEntryCandidate(
                name=name,
                srepr="",
                display=raw,
                type_label="Invalid",
                latex="",
                valid=False,
            )
        )

    def _commit_entry(self, candidate: StoreEntryCandidate) -> bool:
        """Commit one candidate and apply its delta; resync on conflict."""
        assert self._store is not None
        try:
            reply = self._store.commit(CommitRequest(self._revision, candidate))
        except StoreClientError as exc:
            self._log_error(f"Failed to commit variable: {exc}")
            self._reload_from_store()
            return False
        if not reply.ok:
            self._log_error(
                f"Variable store rejected {candidate.name!r}: {reply.message}"
            )
            self._reload_from_store()
            return False
        self._apply_reply(reply)
        self._revision = reply.revision
        return True

    def _apply_reply(self, reply: StoreReply) -> None:
        """Apply a mutation's delta, emitting the matching row signals."""
        delta = reply.delta
        if delta is None:
            return
        for change in delta.changes:
            if change.entry is None:
                self._remove_key(change.name)
            elif change.name in self._entries:
                self._entries[change.name] = change.entry
                self._notify_row(change.name)
            else:
                row = len(self._keys)
                self.beginInsertRows(QModelIndex(), row, row)
                self._keys.append(change.name)
                self._entries[change.name] = change.entry
                self.endInsertRows()
                self.countChanged.emit()
        self._remember_scope_delta(delta)

    def _remove_key(self, name: str) -> None:
        if name not in self._keys:
            return
        row = self._keys.index(name)
        self.beginRemoveRows(QModelIndex(), row, row)
        self._keys.pop(row)
        self._entries.pop(name, None)
        self.endRemoveRows()
        self.countChanged.emit()

    def _reload_from_store(self) -> None:
        """Replace the whole view after a conflict or a lost delta."""
        if self._store is None:
            return
        try:
            snapshot = self._store.snapshot()
        except StoreClientError as exc:
            self._log_error(f"Could not reload variables: {exc}")
            return
        self.beginResetModel()
        self._revision = snapshot.revision
        self._entries = {entry.name: entry for entry in snapshot.entries}
        self._keys = list(self._entries)
        self._scope_history.clear()
        self._last_scope_generation = None
        self._write_scope_generation = None
        self._write_scope_revision = None
        self.endResetModel()
        self.countChanged.emit()

    def _emit_warning(self, entry: StoreEntry) -> None:
        if entry.warning:
            warning = localize_warning(entry.name, entry.warning)
            self.warningOccurred.emit(entry.name, warning)
            self._log_warn(warning)

    def _warn_reserved(self, name: str) -> None:
        """Emit the warning for a name input's meaning depends on.

        A SymPy built-in changes what an expression resolves to; a plotting
        variable changes what the plot reads. Both are stored anyway — the
        warning is the whole of the consequence, as it always was for built-ins.
        """
        from ..model.variable import reserved_name_warning

        warning = reserved_name_warning(name)
        if warning is None:
            return
        warning = localize_warning(name, warning)
        self.warningOccurred.emit(name, warning)
        self._log_warn(warning)

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of variables."""
        return 0 if parent.isValid() else len(self._keys)

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the fixed column count (name, expression, type)."""
        return 0 if parent.isValid() else 3

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        """Return data for the given index and role.

        While a write is in flight the expression cell shows the text the user
        submitted, not the value the manager still holds; the type cell keeps its
        committed label so the row is not dressed up as a finished variable.
        """
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._keys):
            return None
        name = self._keys[row]
        if self._store is not None:
            entry = self._entries.get(name)
            if entry is None:
                return None
            if role == Qt.DisplayRole:
                pending = self._pending.get(name)
                if pending is not None and index.column() == 1:
                    return pending.text
                return (entry.name, entry.display, entry.type_label)[index.column()]
            return None
        entry = self._manager.entry(name)
        if entry is None:
            return None
        if role == Qt.DisplayRole:
            pending = self._pending.get(name)
            if pending is not None and index.column() == 1:
                return pending.text
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
        """Insert or update a valid legacy entry, notifying granularly."""
        if self._store is not None:
            raise RuntimeError("store-backed variables must use commit_candidate")
        is_new = not self._manager.exists(name)
        self._manager.save(name, value)
        self._after_mutation(name, is_new)

    def save_invalid(self, name: str, raw_expr: str) -> None:
        """Insert or update an invalid legacy entry, notifying granularly."""
        if self._store is not None:
            raise RuntimeError("store-backed variables must commit an invalid candidate")
        is_new = not self._manager.exists(name)
        self._manager.save_invalid(name, raw_expr)
        self._after_mutation(name, is_new)

    def rename(self, old_name: str, new_name: str) -> bool:
        """Rename a variable, preserving its row position."""
        if old_name not in self._keys:
            return False
        if self._store is not None:
            old_entry = self._entries.get(old_name)
            old_row = self._keys.index(old_name)
            try:
                reply = self._store.rename(old_name, new_name, self._revision)
            except StoreClientError as exc:
                self._log_error(f"Failed to rename variable: {exc}")
                self._reload_from_store()
                raise ValueError(str(exc)) from None
            if not reply.ok:
                raise ValueError(reply.message or f"cannot rename to {new_name!r}")
            if reply.delta is None:
                return True
            new_entry = next(
                (change.entry for change in reply.delta.changes
                 if change.name == new_name and change.entry is not None),
                None,
            )
            self._remove_key(old_name)
            if new_entry is not None:
                row = min(old_row, len(self._keys))
                self.beginInsertRows(QModelIndex(), row, row)
                self._keys.insert(row, new_name)
                self._entries[new_name] = new_entry
                self.endInsertRows()
                self.countChanged.emit()
                self._revision = reply.revision
                self._remember_scope_delta(reply.delta)
            else:
                self._reload_from_store()
            self._log_info(f"Variable renamed: {old_name} -> {new_name}")
            if old_entry is not None:
                self._emit_warning(old_entry)
            # Renaming *to* a built-in/plotting name is the same collision as
            # creating it: the Store's rename clears the entry's warning, so ask
            # the name table about the new name explicitly (the legacy path below
            # already did).
            self._warn_reserved(new_name)
            return True

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
        if self._store is not None:
            entry = self._entries.get(name)
            try:
                reply = self._store.delete(name, self._revision)
            except StoreClientError as exc:
                self._log_error(f"Failed to delete variable: {exc}")
                self._reload_from_store()
                return False
            if not reply.ok:
                return False
            self._remove_key(name)
            self._revision = reply.revision
            self._remember_scope_delta(reply.delta)
            self._log_info(f"Variable deleted: {name}")
            if entry is not None:
                self._emit_warning(entry)
            return True

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
            name = self._keys[row]
            if self._store is not None:
                entry = self._entries.get(name)
                if entry is None:
                    return ""
                pending = self._pending.get(name)
                if pending is not None and column == 1:
                    return pending.text
                return (entry.name, entry.display, entry.type_label)[column]
            entry = self._manager.entry(name)
            if entry:
                pending = self._pending.get(name)
                if pending is not None and column == 1:
                    return pending.text
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
            name = self._keys[row]
            if name in self._pending:
                return ""  # the panel shows the pending raw text instead
            if self._store is not None:
                entry = self._entries.get(name)
                return entry.latex if entry is not None and entry.valid else ""
            entry = self._manager.entry(name)
            if entry is not None and entry.valid:
                from ..model import render_latex_definition

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
    #: The Variables worker queue became busy or idle (the page's spinner).
    busyChanged = Signal()

    def __init__(
        self,
        variable_manager: Any | None = None,
        log: LogViewModel | None = None,
        calculator: Any | None = None,
        backend: QObject | None = None,
        store: StoreClient | None = None,
        parent: QObject | None = None,
    ):
        """Initialize the variables viewmodel.

        ``store`` is the application's Store worker client: the table reads
        Store strings and writes commit candidates. Without it (tests/headless)
        writes run through ``calculator`` and the legacy manager.
        """
        super().__init__(parent)
        self._variable_manager = variable_manager
        self._log = log
        self._backend = backend
        if calculator is not None:
            self._calculator = calculator
        elif store is not None:
            self._calculator = None
        else:
            from ..model.calculator import Calculator

            self._calculator = Calculator()
        self._filter = None
        self._latex_style = LatexStyle()
        #: ``(latex, style) -> {url, width, height}`` for the details panel. The
        #: page calls `latexFor` from a binding forced by `dataRevision`; a row
        #: that did not change re-asks for the same artwork, and a ziamath render
        #: is ~7 ms. Small and bounded: one selected row at a time.
        self._preview_cache: dict[tuple[str, LatexStyle], dict] = {}
        self._model = VariablesModel(
            variable_manager, log, self._calculator,
            backend=backend, store=store, parent=self,
        )
        self._model.warningOccurred.connect(self.warningOccurred)
        self._model.variableAdded.connect(self.variableAdded)
        self._model.activity.connect(self._touch_backend)
        self._model.busyChanged.connect(self.busyChanged)
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(BACKEND_IDLE_MS)
        self._idle_timer.timeout.connect(self._stop_idle_backend)

    def _get_model(self) -> VariablesModel:
        return self._model

    model = Property(QObject, _get_model, constant=True)

    def is_store_backed(self) -> bool:
        return self._model.is_store_backed()

    def scope_snapshot(self):
        """The Store snapshot (or legacy mapping) a calculation must use."""
        return self._model.scope_snapshot()

    def scope_for(self, generation: int, sent_revision: int | None):
        """The delta/snapshot that brings a worker generation up to date."""
        return self._model.scope_for(generation, sent_revision)

    def set_parse_policy(self, policy: ParsePolicy) -> None:
        """Use ``policy`` for subsequent variable writes."""
        self._model.set_parse_policy(policy)

    def _get_busy(self) -> bool:
        """True while the Variables worker is running or has queued writes."""
        return self._model.is_busy()

    #: Drives the page's calculation spinner and abort button.
    busy = Property(bool, _get_busy, notify=busyChanged)

    @Slot(result=bool)
    def cancelPending(self) -> bool:
        """Abort the running Variables request; the raw draft stays Invalid."""
        return self._model.cancel_active()

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

    @Slot(int, result=bool)
    def isPending(self, row: int) -> bool:
        """True while the visible row's expression is a draft, not committed."""
        if self._filter is None or row < 0:
            return False
        name = self._filter.nameAt(row)
        return self._model.is_pending(name) if name else False

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
        existing = set(self._model.names())
        counter = 1
        while True:
            name = f"var_{counter}"
            if name not in pending and name not in existing:
                return name
            counter += 1

    def _touch_backend(self) -> None:
        if self._backend is None:
            return
        # A QCoreApplication can outlive its dispatcher during teardown; a timer
        # started then would only print "event dispatcher destroyed".
        if (QCoreApplication.instance() is not None
                and QAbstractEventDispatcher.instance() is not None
                and not QCoreApplication.closingDown()):
            self._start_idle_timer()

    def _start_idle_timer(self) -> None:
        try:
            self._idle_timer.start()
        except RuntimeError:
            pass

    def _stop_idle_timer(self) -> None:
        try:
            self._idle_timer.stop()
        except RuntimeError:
            pass

    @Slot()
    def stopBackendIfIdle(self) -> None:
        """Reclaim the Variables worker when the page is idle or being left."""
        self._stop_idle_backend()

    def _stop_idle_backend(self) -> None:
        if self._backend is None:
            return
        if self._model.is_idle():
            self._backend.shutdown()
            self._stop_idle_timer()
        else:
            # A write is still queued/running; check again after another window.
            self._touch_backend()
