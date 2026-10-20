# coding: utf-8
"""The frontend/backend boundary for calculation requests.

The UI never evaluates sympy on its event loop. A backend receives one request
at a time and reports the model's ``Success | Failure`` **and its variant rows**
through Qt signals; the variants are computed here because ``doit``, ``expand``
and ``factor`` are symbolic work and share the request's deadline.
Two implementations share the contract:

* :class:`InlineBackend` runs the model synchronously in this process. It is
  the default when no backend is supplied, which keeps the headless tests and
  any embedding caller deterministic; it has no timeout.
* :class:`ProcessBackend` runs :mod:`python.backend_worker` in a spawned
  process. A request that misses its deadline is reported as ``timedOut`` and
  the process is terminated — Python cannot interrupt sympy in a thread, so a
  separate process is the only place a hard timeout can be enforced.

The viewmodel allocates the request id before submitting, so a synchronous
backend and an asynchronous one follow the same path. Stale ids are ignored by
the caller.
"""

import multiprocessing
import time
from typing import Any, Mapping, Optional

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal

from ..backend_worker import worker_main
from ..model.calculator import Calculator, Success
from ..model.variants import variants


class InlineBackend(QObject):
    """Synchronous backend: evaluate in-process, emit the result immediately.

    No timeout: a runaway request blocks the caller exactly as it did before
    the backend existed. Tests and headless callers use this; the application
    passes a :class:`ProcessBackend`.
    """

    finished = Signal(int, object, object)
    timedOut = Signal(int)
    failed = Signal(int, str)

    timeout_seconds = 0.0

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._calculator = Calculator()

    def submit(
        self,
        request_id: int,
        kind: str,
        payload: Any,
        scope: Mapping[str, Any],
    ) -> None:
        """Evaluate now and emit the outcome before returning."""
        try:
            if kind == "evaluate":
                result = self._calculator.evaluate(payload, scope)
            else:
                result = self._calculator.assign(payload, scope)
        except Exception as exc:  # noqa: BLE001 - a crash is a report, not a raise
            self.failed.emit(request_id, f"{type(exc).__name__}: {exc}")
        else:
            variant_rows = ()
            if isinstance(result, Success):
                try:
                    variant_rows = variants(result.value)
                except Exception:  # noqa: BLE001 - no card, not a failed answer
                    variant_rows = ()
            self.finished.emit(request_id, result, variant_rows)

    def cancel(self) -> None:
        """Nothing to cancel: `submit` has already returned."""

    def shutdown(self) -> None:
        """Nothing to release."""


class ProcessBackend(QObject):
    """Calculation in a spawned process, with a hard timeout.

    The worker is started lazily and reused between successful requests. A
    timeout, a crash or a broken pipe terminates it; the next request starts a
    fresh one. One request may be in flight at a time — a new ``submit`` cancels
    the previous one, so typing a correction never waits for the old deadline.
    """

    finished = Signal(int, object, object)
    timedOut = Signal(int)
    failed = Signal(int, str)

    #: A request older than this is terminated. The boundary reports it as a
    #: timeout; the model never sees it.
    timeout_seconds: float

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.timeout_seconds = float(timeout_seconds)
        self._context = multiprocessing.get_context("spawn")
        self._process: Optional[multiprocessing.Process] = None
        self._connection = None
        self._active_id: Optional[int] = None
        self._deadline = 0.0

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(20)
        self._poll_timer.timeout.connect(self._poll)

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    def submit(
        self,
        request_id: int,
        kind: str,
        payload: Any,
        scope: Mapping[str, Any],
    ) -> None:
        """Send one request, replacing anything already in flight."""
        self.cancel()
        try:
            self._ensure_worker()
            self._connection.send((request_id, kind, payload, scope))
        except Exception as exc:  # noqa: BLE001 - start/pipe failure is a status
            self._stop_worker()
            self._active_id = None
            self._poll_timer.stop()
            self.failed.emit(request_id, f"{type(exc).__name__}: {exc}")
            return

        self._active_id = request_id
        self._deadline = (
            time.monotonic() + self.timeout_seconds
            if self.timeout_seconds > 0
            else float("inf")
        )
        self._poll_timer.start()

    def cancel(self) -> None:
        """Abandon the current request and terminate its worker, if any."""
        self._poll_timer.stop()
        if self._active_id is None:
            return
        self._active_id = None
        self._stop_worker()

    def shutdown(self) -> None:
        """Stop the poll and terminate the worker (application exit)."""
        self._poll_timer.stop()
        self._active_id = None
        self._stop_worker()

    def _ensure_worker(self) -> None:
        """Start the child if it is missing or no longer alive."""
        if (self._process is not None
                and self._process.is_alive()
                and self._connection is not None):
            return
        self._stop_worker()
        parent_connection, child_connection = self._context.Pipe()
        process = self._context.Process(
            target=worker_main,
            args=(child_connection,),
            daemon=True,
        )
        process.start()
        child_connection.close()
        self._process = process
        self._connection = parent_connection

    def _stop_worker(self) -> None:
        """Terminate and reap the child; idempotent and never raises."""
        connection, process = self._connection, self._process
        self._connection = None
        self._process = None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
        if process is None:
            return
        if process.is_alive():
            process.terminate()
        process.join(0.5)
        if process.is_alive():
            process.kill()
            process.join(0.5)

    def _poll(self) -> None:
        """Read one reply, or enforce the deadline."""
        request_id = self._active_id
        if request_id is None:
            self._poll_timer.stop()
            return

        connection = self._connection
        if connection is None:
            self._fail(request_id, "the calculation backend is not running")
            return

        try:
            if connection.poll(0):
                reply_id, result, variant_rows = connection.recv()
                if reply_id != request_id:
                    return
                self._poll_timer.stop()
                self._active_id = None
                self.finished.emit(request_id, result, variant_rows)
                return
        except (EOFError, OSError) as exc:
            self._fail(request_id, f"the calculation backend stopped ({exc})")
            return

        if time.monotonic() >= self._deadline:
            self._poll_timer.stop()
            self._active_id = None
            self._stop_worker()
            self.timedOut.emit(request_id)

    def _fail(self, request_id: int, message: str) -> None:
        """Report a dead/unsynchronised worker and drop it."""
        self._poll_timer.stop()
        self._active_id = None
        self._stop_worker()
        self.failed.emit(request_id, message)
