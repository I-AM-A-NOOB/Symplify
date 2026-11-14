"""One spawned child behind a pickled duplex pipe (zero Qt).

Both long-lived children in the app need the same lifecycle: spawn with the
``spawn`` context, keep one end of a duplex pipe, optionally contain the process
(Windows Job Object; POSIX rlimits are applied by the child itself), terminate
and reap without ever raising, and do it again after a crash.

The Qt side stays in the services: polling, deadlines and the request protocol
belong to the conversation, not to the process. Keeping the lifecycle here is
what stops the calculation backend and the LaTeX renderer from growing two
slightly different reapers.
"""

from __future__ import annotations

import multiprocessing
import threading
from collections.abc import Callable, Sequence
from typing import Any

from . import sandbox

#: How long a synchronous reap may wait for one stage before escalating.
REAP_SECONDS = 0.5


class ChildProcess:
    """A spawned process and the parent's end of its pipe.

    ``args`` may be a callable: it is asked for the child's extra arguments on
    every start, with the spawn context, so state that must be recreated per
    process (a shared generation array, say) is created by the same context the
    process comes from.
    """

    def __init__(
        self,
        target: Callable[..., None],
        args: Sequence[Any] | Callable[[Any], Sequence[Any]] = (),
        *,
        sandboxed: bool = False,
    ) -> None:
        """Remember what to start; nothing is spawned until :meth:`ensure`."""
        self._target: Callable[..., None] = target
        self._args = args
        self._sandboxed: bool = sandboxed
        self._context: Any = multiprocessing.get_context("spawn")
        self._process: Any = None
        self._connection: Any = None
        self._job: Any = None

    @property
    def context(self) -> Any:
        """The spawn context every start uses (for argparse-free shared state)."""
        return self._context

    @property
    def connection(self) -> Any:
        """The parent's pipe end, or None while no child is running."""
        return self._connection

    @property
    def alive(self) -> bool:
        """True while the spawned process is still running."""
        return self._process is not None and self._process.is_alive()

    def ensure(self) -> Any:
        """Start the child if needed and return the parent's pipe end."""
        if self.alive and self._connection is not None:
            return self._connection
        self.stop()
        parent, child = self._context.Pipe()
        extra: Sequence[Any] = (
            self._args(self._context) if callable(self._args) else self._args
        )
        process = self._context.Process(
            target=self._target,
            args=(child, *extra),
            daemon=True,
        )
        process.start()
        child.close()
        self._process = process
        self._connection = parent
        if self._sandboxed:
            job = sandbox.create_job()
            if job is not None:
                if process.pid is not None and job.assign(process.pid):
                    self._job = job
                else:
                    job.close()
        return parent

    def send(self, message: Any) -> None:
        """Send one message to the child, starting it if needed."""
        self.ensure().send(message)

    def stop(self, *, wait: bool = True) -> None:
        """Terminate and reap the child; idempotent and never raising.

        Args:
            wait: Reap on this thread. False hands the termination to a daemon
                thread, for callers whose work is already done and must not
                block on a slow reap.
        """
        job, self._job = self._job, None
        connection, self._connection = self._connection, None
        process, self._process = self._process, None
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
                    process.join(REAP_SECONDS)
                    if process.is_alive():
                        process.kill()
                        process.join(REAP_SECONDS)
            except Exception:  # noqa: BLE001 - retirement is best effort
                pass

        if wait:
            reap()
        else:
            threading.Thread(target=reap, daemon=True).start()
