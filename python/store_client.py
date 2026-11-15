"""Blocking client for the Store worker (zero Qt, zero SymPy).

The Store is fast, string-only and single-writer, so the composition root and
the Variables page can afford a synchronous request/response per operation: the
Compute worker keeps the long-running work, and no Store request has to race a
calculation. The client still talks to the spawned worker over the pickled pipe,
so the UI process never owns the only copy of the variables.

This is deliberately not a QObject. Qt callers receive plain ``StoreReply`` /
``ScopeSnapshot`` values and apply them; a future asynchronous client can keep
the same methods' meaning.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .child_process import ChildProcess
from .store_worker import worker_main
from .worker_protocol import (
    CommitRequest,
    ScopeSnapshot,
    StoreEntryCandidate,
    StoreReply,
)

#: A fresh install shows the plotting names in the Variables table. Marking
#: them here keeps the composition root free of SymPy; `plotting.PLOT_SYMBOLS`
#: is the model's copy of the same two names.
PLOTTING_NAMES = ("x", "y")


class StoreClientError(RuntimeError):
    """The Store worker could not answer, or answered malformed data."""


class StoreClientTimeout(StoreClientError):
    """The Store worker missed the client's deadline and was replaced."""


def plotting_seeds() -> tuple[StoreEntryCandidate, ...]:
    """String-only seeds for a fresh Store (the two plotting variables)."""
    return tuple(
        StoreEntryCandidate(
            name=name,
            srepr=f"Symbol('{name}')",
            display=name,
            type_label="Symbol",
            latex=name,
        )
        for name in PLOTTING_NAMES
    )


class StoreClient:
    """A synchronous owner of one spawned Store worker."""

    def __init__(
        self,
        snapshot_path: str | Path | None = None,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._worker = ChildProcess(worker_main, (snapshot_path,), sandboxed=True)
        self._timeout_seconds = float(timeout_seconds)
        self._request_id = 0
        #: The last failure, for the log/status surface; empty after a success.
        self.last_error = ""
        #: How many requests have hit the deadline (the worker is replaced).
        self.timeout_count = 0

    def snapshot(self) -> ScopeSnapshot:
        return self._request("snapshot", None)

    def commit(self, request: CommitRequest) -> StoreReply:
        return self._request("commit", request)

    def rename(self, old_name: str, new_name: str, expected_revision: int) -> StoreReply:
        return self._request("rename", (old_name, new_name, expected_revision))

    def delete(self, name: str, expected_revision: int) -> StoreReply:
        return self._request("delete", (name, expected_revision))

    def clear(self, expected_revision: int) -> StoreReply:
        return self._request("clear", expected_revision)

    def bootstrap(self, seeds: Iterable[StoreEntryCandidate] = ()) -> ScopeSnapshot:
        """Start the worker and seed a truly fresh Store with ``seeds``.

        A snapshot with entries is persistence winning; a snapshot with a
        non-zero revision but no entries is a deliberate clear, not a fresh
        install, so neither is re-seeded.
        """
        snapshot = self.snapshot()
        if snapshot.entries or snapshot.revision:
            return snapshot
        for seed in seeds:
            reply = self.commit(CommitRequest(snapshot.revision, seed))
            if not reply.ok:
                raise StoreClientError(reply.message or "the Store rejected a seed")
            snapshot = self.snapshot()
        return snapshot

    def close(self) -> None:
        self._worker.stop()

    def _request(self, operation: str, payload: Any) -> Any:
        self._request_id += 1
        request_id = self._request_id
        self.last_error = ""
        try:
            connection = self._worker.ensure()
            connection.send((request_id, operation, payload))
            if not connection.poll(self._timeout_seconds):
                # The worker may still answer later; leaving it alive would put
                # the next request one reply behind, so replace it instead.
                self._worker.stop()
                self.timeout_count += 1
                self.last_error = f"the Store did not answer {operation!r}"
                raise StoreClientTimeout(self.last_error)
            message = connection.recv()
        except StoreClientError:
            raise
        except (EOFError, OSError) as exc:
            self._worker.stop()
            self.last_error = f"the Store worker stopped: {exc}"
            raise StoreClientError(self.last_error) from None
        try:
            reply_id, phase, value = message
        except (TypeError, ValueError) as exc:
            self._worker.stop()
            self.last_error = f"malformed Store reply: {exc}"
            raise StoreClientError(self.last_error) from None
        if reply_id != request_id:
            self._worker.stop()
            self.last_error = (
                f"Store replied to request {reply_id}, expected {request_id}"
            )
            raise StoreClientError(self.last_error)
        if phase == "error":
            self.last_error = str(value)
            raise StoreClientError(self.last_error)
        if phase == "snapshot" and operation != "snapshot":
            self._worker.stop()
            self.last_error = f"unexpected snapshot reply for {operation!r}"
            raise StoreClientError(self.last_error)
        if phase == "reply" and operation == "snapshot":
            self._worker.stop()
            self.last_error = "unexpected mutation reply for 'snapshot'"
            raise StoreClientError(self.last_error)
        return value
