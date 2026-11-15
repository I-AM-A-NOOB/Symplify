"""The variable Store's child process (zero Qt, zero SymPy).

The Store is the single writer of variable state. It stores only strings: the
Compute worker owns every SymPy object and receives a :class:`ScopeSnapshot` or
:class:`ScopeDelta` from here. This module must therefore never import
:mod:`python.model` (which loads SymPy) or Qt; the worker is spawned and can be
tested without either.

Protocol (both directions): ``(request_id, ...)``.
- Parent -> child:
  - ``(request_id, "snapshot", None)``
  - ``(request_id, "commit", CommitRequest)``
  - ``(request_id, "rename", (old_name, new_name, expected_revision))``
  - ``(request_id, "delete", (name, expected_revision))``
  - ``(request_id, "clear", expected_revision)``
  - ``None`` asks the worker to exit.
- Child -> parent:
  - ``(request_id, "snapshot", ScopeSnapshot)`` for ``snapshot``;
  - ``(request_id, "reply", StoreReply)`` for a mutation;
  - ``(request_id, "error", message)`` for a malformed request. The worker
    stays alive with its state unchanged.

Every mutation is guarded by the caller's ``expected_revision``. A stale writer
gets ``StoreReply(ok=False, revision=<current>)`` and no state change; a
successful mutation returns the exact ``ScopeDelta`` to apply to the Compute
cache. An optional JSON snapshot is written atomically after each mutation; a
failed write is reported in ``StoreReply.message`` but never rolls back the
in-memory write (the worker is the authoritative state).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .names import SYMPY_VERSION, validate_name
from .sandbox import apply_worker_limits
from .worker_protocol import (
    CommitRequest,
    ScopeChange,
    ScopeDelta,
    ScopeSnapshot,
    StoreEntry,
    StoreReply,
)


class VariableStore:
    """The authoritative in-memory variables plus their revisions.

    All values are strings/booleans; the class never parses an expression. It
    is deliberately usable without a worker for unit tests and for callers that
    want a synchronous store.
    """

    def __init__(self, snapshot_path: str | Path | None = None) -> None:
        self._path = None if snapshot_path is None else Path(snapshot_path)
        self._entries: dict[str, StoreEntry] = {}
        self._revision = 0
        #: Why a previously saved snapshot was ignored, if it was unusable.
        self.load_error = ""
        self.load()

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def path(self) -> Path | None:
        return self._path

    def entry(self, name: str) -> StoreEntry | None:
        return self._entries.get(name)

    def entries(self) -> tuple[StoreEntry, ...]:
        """Every entry in insertion order (the table's order)."""
        return tuple(self._entries.values())

    def snapshot(self) -> ScopeSnapshot:
        return ScopeSnapshot(self._revision, self.entries())

    # --- mutations --------------------------------------------------------

    def commit(self, request: CommitRequest) -> StoreReply:
        """Commit one computed candidate, assigning it the next revision."""
        conflict = self._check_expected(request.expected_revision)
        if conflict is not None:
            return conflict
        if not validate_name(request.entry.name):
            return StoreReply(
                False,
                self._revision,
                None,
                f"invalid variable name: {request.entry.name!r}",
            )
        revision = self._revision + 1
        entry = request.entry.to_entry(revision)
        self._entries[entry.name] = entry
        self._revision = revision
        delta = ScopeDelta(
            revision - 1,
            revision,
            (ScopeChange(entry.name, revision, entry),),
        )
        return self._stored(delta)

    def rename(self, old_name: str, new_name: str, expected_revision: int) -> StoreReply:
        """Rename a variable, preserving its position and recoverable value.

        ``latex`` and ``warning`` are cleared: both are display strings that may
        depend on the name, and the Store cannot recompute them without SymPy.
        The Compute worker can refresh them on the next request.
        """
        conflict = self._check_expected(expected_revision)
        if conflict is not None:
            return conflict
        if old_name not in self._entries:
            return StoreReply(
                False, self._revision, None, f"no variable named {old_name!r}")
        if not validate_name(new_name):
            return StoreReply(
                False, self._revision, None, f"invalid variable name: {new_name!r}")
        if new_name == old_name:
            return StoreReply(True, self._revision, None)

        old = self._entries[old_name]
        if new_name in self._entries:
            return StoreReply(
                False, self._revision, None,
                f"variable {new_name!r} already exists",
            )

        revision = self._revision + 1
        renamed = StoreEntry(
            name=new_name,
            srepr=old.srepr,
            display=old.display,
            type_label=old.type_label,
            latex="",
            revision=revision,
            valid=old.valid,
            warning="",
        )
        self._entries = {
            (new_name if key == old_name else key): (
                renamed if key == old_name else entry
            )
            for key, entry in self._entries.items()
        }
        self._revision = revision
        delta = ScopeDelta(
            revision - 1,
            revision,
            (
                ScopeChange(old_name, revision, None),
                ScopeChange(new_name, revision, renamed),
            ),
        )
        return self._stored(delta)

    def delete(self, name: str, expected_revision: int) -> StoreReply:
        conflict = self._check_expected(expected_revision)
        if conflict is not None:
            return conflict
        if name not in self._entries:
            return StoreReply(False, self._revision, None, f"no variable named {name!r}")
        revision = self._revision + 1
        del self._entries[name]
        self._revision = revision
        delta = ScopeDelta(
            revision - 1,
            revision,
            (ScopeChange(name, revision, None),),
        )
        return self._stored(delta)

    def clear(self, expected_revision: int) -> StoreReply:
        conflict = self._check_expected(expected_revision)
        if conflict is not None:
            return conflict
        if not self._entries:
            return StoreReply(True, self._revision, None)
        names = tuple(self._entries)
        revision = self._revision + 1
        self._entries.clear()
        self._revision = revision
        delta = ScopeDelta(
            revision - 1,
            revision,
            tuple(ScopeChange(name, revision, None) for name in names),
        )
        return self._stored(delta)

    # --- persistence ------------------------------------------------------

    def load(self) -> None:
        """Load the optional snapshot; an unusable file is set aside, not kept.

        A corrupt file is moved to ``<name>.corrupt`` rather than overwritten:
        the app starts with no variables, but the failed data is still on disk
        for a human to inspect. ``load_error`` carries the reason.
        """
        self.load_error = ""
        path = self._path
        if path is None or not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "snapshot" in data:
                version = str(data.get("sympy_version", ""))
                if version and version != SYMPY_VERSION:
                    raise ValueError(
                        f"snapshot was written by SymPy {version}; "
                        f"this build uses {SYMPY_VERSION}"
                    )
                data = data["snapshot"]
            snapshot = ScopeSnapshot.from_dict(data)
            if not all(validate_name(entry.name) for entry in snapshot.entries):
                raise ValueError("snapshot contains an invalid variable name")
        except (OSError, ValueError) as exc:
            self.load_error = f"variable snapshot not loaded: {exc}"
            self._set_aside(path)
            return
        self._revision = snapshot.revision
        self._entries = {entry.name: entry for entry in snapshot.entries}

    def _save(self) -> str:
        """Write atomically; return an error sentence or an empty string."""
        path = self._path
        if path is None:
            return ""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "sympy_version": SYMPY_VERSION,
                        "snapshot": self.snapshot().to_dict(),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError as exc:
            return f"variable snapshot not written: {exc}"
        return ""

    def _set_aside(self, path: Path) -> None:
        try:
            os.replace(path, path.with_suffix(path.suffix + ".corrupt"))
        except OSError:
            pass

    # --- internals --------------------------------------------------------

    def _check_expected(self, expected_revision: int) -> StoreReply | None:
        if (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise ValueError("expected_revision must be a non-negative integer")
        if expected_revision == self._revision:
            return None
        return StoreReply(
            False,
            self._revision,
            None,
            f"revision conflict: expected {expected_revision}, "
            f"store is at {self._revision}",
        )

    def _stored(self, delta: ScopeDelta) -> StoreReply:
        message = self._save()
        return StoreReply(True, self._revision, delta, message)


def worker_main(connection: Any, snapshot_path: str | Path | None = None) -> None:
    """Serve Store requests until the parent closes the pipe."""
    apply_worker_limits()
    store = VariableStore(snapshot_path)
    try:
        while True:
            try:
                request = connection.recv()
            except (EOFError, OSError):
                return
            if request is None:
                return
            try:
                request_id, operation, payload = request
            except (TypeError, ValueError) as exc:
                try:
                    connection.send((None, "error", f"malformed request: {exc}"))
                except (BrokenPipeError, EOFError, OSError):
                    return
                continue

            try:
                if operation == "snapshot":
                    response = ("snapshot", store.snapshot())
                elif operation == "commit":
                    response = ("reply", store.commit(payload))
                elif operation == "rename":
                    old_name, new_name, expected = payload
                    response = ("reply", store.rename(old_name, new_name, expected))
                elif operation == "delete":
                    name, expected = payload
                    response = ("reply", store.delete(name, expected))
                elif operation == "clear":
                    response = ("reply", store.clear(payload))
                else:
                    response = ("error", f"unknown store operation {operation!r}")
            except Exception as exc:  # noqa: BLE001 - report, never escape
                response = ("error", f"{type(exc).__name__}: {exc}")

            try:
                connection.send((request_id, *response))
            except (BrokenPipeError, EOFError, OSError):
                return
    finally:
        try:
            connection.close()
        except OSError:
            pass
