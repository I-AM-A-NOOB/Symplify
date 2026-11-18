"""The frontend/backend boundary for calculation requests.

The UI never evaluates sympy on its event loop. The application uses
:class:`ProcessBackend`, which runs the calculation worker in a spawned process;
a request that misses its deadline is reported as ``timedOut`` and the process
is terminated — Python cannot interrupt sympy in a thread, so a separate
process is the only place a hard timeout can be enforced. The worker replies
with plain-data :class:`~python.worker_protocol.ResultView` and
:class:`~python.worker_protocol.VariantView` values, never a SymPy object.

The synchronous test/headless backend lives in
:mod:`python.viewmodel.inline_backend`, so importing this module does not load
SymPy into the UI process. The viewmodel allocates the request id before
submitting, so a synchronous backend and an asynchronous one follow the same
path. Stale ids are ignored by the caller.
"""

import time
from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal

from ..backend_entry import worker_main
from ..child_process import ChildProcess
from ..worker_protocol import ParsePolicy, ScopeDelta, ScopeSnapshot


class ProcessBackend(QObject):
    """Calculation in a spawned process, with a hard timeout.

    The worker is started lazily and reused between successful requests. A
    timeout, a crash or a broken pipe terminates it; the next request starts a
    fresh one. One request may be in flight at a time — a new ``submit`` cancels
    the previous one, so typing a correction never waits for the old deadline.
    A ``variable`` request is the Variables page's assign: the worker answers
    with the result only, so the next queued write can reuse the same process
    without waiting for optional variants.
    """

    finished = Signal(int, object)
    variantsReady = Signal(int, object)
    timedOut = Signal(int)
    failed = Signal(int, str)
    cancelled = Signal(int)

    #: A request older than this is terminated. The boundary reports it as a
    #: timeout; the model never sees it.
    timeout_seconds: float

    #: Variants are optional and arrive after the result. A slow `doit()` or
    #: `factor()` must not keep the result's state "calculating", so this window
    #: is independent of `timeout_seconds`.
    VARIANTS_TIMEOUT_SECONDS = 2.0

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.timeout_seconds = float(timeout_seconds)
        #: The parser policy sent with every request. The worker applies it
        #: before evaluating; changing it never needs a worker restart.
        self._parse_policy = ParsePolicy()
        #: The spawned worker and its pipe; the supervisor owns spawn, containment
        #: (Windows Job Object) and the reaper.
        self._worker = ChildProcess(worker_main, sandboxed=True)
        self._active_id: int | None = None
        self._deadline = 0.0
        #: Bumped whenever the worker is replaced, so the scope sender knows to
        #: send a snapshot instead of a delta.
        self._generation = 0
        self._worker_started = False
        #: ``variable`` writes send a result only; other kinds are followed by
        #: their optional variant rows.
        self._expect_variants = True
        #: The result was already delivered; this id only waits for its optional
        #: variant rows. It is never reported through `timedOut`/`failed`.
        self._variants_id: int | None = None
        self._variants_deadline = 0.0

        self._poll_timer = QTimer(self)
        # The timer is only a completion check while a request is in flight.
        # 20 ms was a floor under every cheap calculation; 2 ms is below what
        # a person can detect and still costs nothing while idle.
        self._poll_timer.setInterval(2)
        self._poll_timer.timeout.connect(self._poll)

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    @property
    def generation(self) -> int:
        """The identity of the current worker; changes on every replacement."""
        if self._worker_started and not self._worker.alive:
            # An idle worker died; the next send will start a fresh one.
            self._worker_started = False
            self._generation += 1
        return self._generation

    def set_parse_policy(self, policy: ParsePolicy) -> None:
        """Set the parser policy carried by subsequent requests."""
        if not isinstance(policy, ParsePolicy):
            raise TypeError(
                f"parse_policy must be ParsePolicy, got {type(policy).__name__}"
            )
        self._parse_policy = policy

    def warm_up(self) -> None:
        """Start the worker before the first request, hiding SymPy's import.

        Failure is deliberately silent: the first real submission retries the
        same startup path and reports any error through its normal `failed`
        signal. `InlineBackend` has no equivalent.
        """
        try:
            self._worker.ensure()
            self._worker_started = True
        except Exception:  # noqa: BLE001 - warm-up is optional
            self._stop_worker()

    def submit(
        self,
        request_id: int,
        kind: str,
        payload: Any,
        scope: Mapping[str, Any] | ScopeSnapshot | ScopeDelta,
    ) -> None:
        """Send one request, replacing anything already in flight."""
        self.cancel()
        self._expect_variants = kind != "variable"
        try:
            self._worker.send(
                (request_id, kind, payload, scope, self._parse_policy)
            )
            self._worker_started = True
        except Exception as exc:  # noqa: BLE001 - start/pipe failure is a status
            self._stop_worker()
            self._active_id = None
            self._stop_poll_timer()
            self.failed.emit(request_id, f"{type(exc).__name__}: {exc}")
            return

        self._active_id = request_id
        self._deadline = (
            time.monotonic() + self.timeout_seconds
            if self.timeout_seconds > 0
            else float("inf")
        )
        self._start_poll_timer()

    def cancel(self, *, notify: bool = False) -> None:
        """Abandon the current request and terminate its worker, if any.

        Pending variants also own the worker: a new request must not wait for a
        slow optional computation from the previous result. ``notify`` is only
        for the user's Cancel button; internal replacement stays silent.
        """
        self._stop_poll_timer()
        if self._active_id is None and self._variants_id is None:
            return
        active_id = self._active_id
        # Only optional variant rows are pending: their result is already on
        # screen, so the next request must not block on this worker's reap.
        retire_async = self._active_id is None
        self._active_id = None
        self._variants_id = None
        self._variants_deadline = 0.0
        if retire_async:
            self._retire_worker_async()
        else:
            self._stop_worker()
        if notify and active_id is not None:
            self.cancelled.emit(active_id)

    def shutdown(self) -> None:
        """Stop the poll and terminate the worker (application exit)."""
        self._stop_poll_timer()
        self._active_id = None
        self._stop_worker()

    def _stop_poll_timer(self) -> None:
        """Stop the poll timer if Qt's C++ object still exists.

        The QML page's `Component.onDestruction` can run after Qt has already
        deleted this backend's QTimer child during application teardown. The
        wrapper remains alive long enough for `shutdown` to be called from both
        `aboutToQuit` and the page, and calling `stop()` on the deleted C++
        object raises rather than being a no-op.
        """
        try:
            self._poll_timer.stop()
        except RuntimeError:
            pass

    def _start_poll_timer(self) -> None:
        """Start polling, unless teardown has already deleted the timer."""
        try:
            self._poll_timer.start()
        except RuntimeError:
            pass

    def _stop_worker(self) -> None:
        """Terminate and reap the child; idempotent and never raises."""
        self._variants_id = None
        self._variants_deadline = 0.0
        self._generation += 1
        self._worker_started = False
        self._worker.stop()

    def _retire_worker_async(self) -> None:
        """Terminate a worker without joining it on the UI thread.

        This is the variants-timeout path: the result is already on screen, and
        stopping a slow optional worker must not freeze the UI while it is
        reaped. The supervisor's daemon thread owns the detached process.
        """
        self._variants_id = None
        self._variants_deadline = 0.0
        self._generation += 1
        self._worker_started = False
        self._worker.stop(wait=False)

    def _poll(self) -> None:
        """Read one reply, or enforce the current deadline.

        A result and its variants are two messages. The result clears
        ``_active_id`` and starts an independent variants deadline; a failure to
        receive the variants is quiet, because the displayed result is already
        complete.
        """
        active_id = self._active_id
        variants_id = self._variants_id
        if active_id is None and variants_id is None:
            self._stop_poll_timer()
            return

        connection = self._worker.connection
        if connection is None:
            if active_id is not None:
                self._fail(active_id, "the calculation backend is not running")
            else:
                self._finish_variants(variants_id)
            return

        try:
            if connection.poll(0):
                reply_id, phase, payload, rows = connection.recv()
                if active_id is not None:
                    if reply_id != active_id:
                        return
                    if phase != "result":
                        return
                    expect_variants = self._expect_variants
                    self._active_id = None
                    if expect_variants:
                        self._variants_id = active_id
                        self._variants_deadline = (
                            time.monotonic() + self.VARIANTS_TIMEOUT_SECONDS
                        )
                    else:
                        self._variants_id = None
                        self._variants_deadline = 0.0
                        self._stop_poll_timer()
                    self.finished.emit(active_id, payload)
                    return

                if reply_id != variants_id:
                    return
                if phase != "variants":
                    return
                self._variants_id = None
                self._variants_deadline = 0.0
                self._stop_poll_timer()
                self.variantsReady.emit(variants_id, rows)
                return
        except (EOFError, OSError) as exc:
            if active_id is not None:
                self._fail(active_id, f"the calculation backend stopped ({exc})")
            else:
                self._finish_variants(variants_id)
            return

        now = time.monotonic()
        if active_id is not None:
            if now >= self._deadline:
                self._stop_poll_timer()
                self._active_id = None
                self._stop_worker()
                self.timedOut.emit(active_id)
        elif now >= self._variants_deadline:
            self._finish_variants(variants_id)

    def _finish_variants(self, request_id: int) -> None:
        """Give up on optional rows without touching the delivered result."""
        self._stop_poll_timer()
        self._variants_id = None
        self._variants_deadline = 0.0
        self._retire_worker_async()
        self.variantsReady.emit(request_id, ())

    def _fail(self, request_id: int, message: str) -> None:
        """Report a dead/unsynchronised worker and drop it."""
        self._stop_poll_timer()
        self._active_id = None
        self._stop_worker()
        self.failed.emit(request_id, message)
