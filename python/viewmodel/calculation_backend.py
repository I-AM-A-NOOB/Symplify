"""The frontend/backend boundary for calculation requests.

The UI never evaluates sympy on its event loop. A backend receives one request
at a time and reports the model's ``Success | Failure`` first, then its optional
variant rows through a separate Qt signal. The variants are computed inside the
backend because ``doit``, ``expand`` and ``factor`` are symbolic work and share
the request's deadline.
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
import threading
import time
from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal

from .. import sandbox
from ..backend_worker import worker_main
from ..model.calculator import Calculator, Success
from ..model.variants import variants


class InlineBackend(QObject):
    """Synchronous backend: evaluate in-process, emit the result immediately.

    No timeout: a runaway request blocks the caller exactly as it did before
    the backend existed. Tests and headless callers use this; the application
    passes a :class:`ProcessBackend`.
    """

    finished = Signal(int, object)
    variantsReady = Signal(int, object)
    timedOut = Signal(int)
    failed = Signal(int, str)

    timeout_seconds = 0.0

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._calculator = Calculator()

    def warm_up(self) -> None:
        """Nothing to start: the inline backend runs in this process."""

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
            self.finished.emit(request_id, result)
            variant_rows = ()
            if isinstance(result, Success):
                try:
                    variant_rows = variants(result.value)
                except Exception:  # noqa: BLE001 - no card, not a failed answer
                    variant_rows = ()
            self.variantsReady.emit(request_id, variant_rows)

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

    finished = Signal(int, object)
    variantsReady = Signal(int, object)
    timedOut = Signal(int)
    failed = Signal(int, str)

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
        self._context = multiprocessing.get_context("spawn")
        self._process: multiprocessing.Process | None = None
        self._connection = None
        #: Windows Job Object holding the worker; None on POSIX/where creation
        #: failed. Closing it is also the KILL_ON_JOB_CLOSE cleanup.
        self._job = None
        self._active_id: int | None = None
        self._deadline = 0.0
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

    def warm_up(self) -> None:
        """Start the worker before the first request, hiding SymPy's import.

        Failure is deliberately silent: the first real submission retries the
        same startup path and reports any error through its normal `failed`
        signal. `InlineBackend` has no equivalent.
        """
        try:
            self._ensure_worker()
        except Exception:  # noqa: BLE001 - warm-up is optional
            self._stop_worker()

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
        """Abandon the current request and terminate its worker, if any.

        Pending variants also own the worker: a new request must not wait for a
        slow optional computation from the previous result.
        """
        self._poll_timer.stop()
        if self._active_id is None and self._variants_id is None:
            return
        self._active_id = None
        self._variants_id = None
        self._variants_deadline = 0.0
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

        # The child blocks on recv() until the first request, so assigning the
        # job here has no user work to race with.
        job = sandbox.create_job()
        if job is not None:
            if job.assign(process.pid):
                self._job = job
            else:
                job.close()

    def _stop_worker(self) -> None:
        """Terminate and reap the child; idempotent and never raises."""
        self._variants_id = None
        self._variants_deadline = 0.0
        job, self._job = self._job, None
        if job is not None:
            job.close()
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

    def _retire_worker_async(self) -> None:
        """Terminate a worker without joining it on the UI thread.

        This is the variants-timeout path: the result is already on screen, and
        stopping a slow optional worker must not freeze the UI while it is
        reaped. The detached process/pipe/job are owned by the reaper thread.
        """
        self._variants_id = None
        self._variants_deadline = 0.0
        job, self._job = self._job, None
        connection, process = self._connection, self._process
        self._connection = None
        self._process = None
        if job is None and connection is None and process is None:
            return

        def reap() -> None:
            try:
                if job is not None:
                    job.close()
                if connection is not None:
                    try:
                        connection.close()
                    except OSError:
                        pass
                if process is not None:
                    if process.is_alive():
                        process.terminate()
                    process.join(0.5)
                    if process.is_alive():
                        process.kill()
                        process.join(0.5)
            except Exception:  # noqa: BLE001 - retirement is best effort
                pass

        threading.Thread(target=reap, daemon=True).start()

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
            self._poll_timer.stop()
            return

        connection = self._connection
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
                    self._active_id = None
                    self._variants_id = active_id
                    self._variants_deadline = (
                        time.monotonic() + self.VARIANTS_TIMEOUT_SECONDS
                    )
                    self.finished.emit(active_id, payload)
                    return

                if reply_id != variants_id:
                    return
                if phase != "variants":
                    return
                self._variants_id = None
                self._variants_deadline = 0.0
                self._poll_timer.stop()
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
                self._poll_timer.stop()
                self._active_id = None
                self._stop_worker()
                self.timedOut.emit(active_id)
        elif now >= self._variants_deadline:
            self._finish_variants(variants_id)

    def _finish_variants(self, request_id: int) -> None:
        """Give up on optional rows without touching the delivered result."""
        self._poll_timer.stop()
        self._variants_id = None
        self._variants_deadline = 0.0
        self._retire_worker_async()
        self.variantsReady.emit(request_id, ())

    def _fail(self, request_id: int, message: str) -> None:
        """Report a dead/unsynchronised worker and drop it."""
        self._poll_timer.stop()
        self._active_id = None
        self._stop_worker()
        self.failed.emit(request_id, message)
