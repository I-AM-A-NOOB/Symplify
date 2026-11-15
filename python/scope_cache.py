"""The Compute worker's scope cache: revisions plus restored SymPy objects.

This module is zero SymPy **by injection**: the worker passes
``restore_srepr``; tests pass a fake that records which entries were parsed.
That keeps the cache's bookkeeping testable without importing the calculator and
makes the one SymPy dependency explicit.

The cache pairs a :class:`ScopeState` (the string half from the Store) with
``name -> SymPy object``. A snapshot parses every entry once (a worker restart);
a delta parses only the names whose revision changed. A rejected delta or a
failed restore leaves both halves untouched.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .worker_protocol import ScopeDelta, ScopeSnapshot, ScopeState

__all__ = ["ScopeCache"]


class ScopeCache:
    """The Compute worker's ``name -> restored object`` map at one revision."""

    def __init__(self, restore: Callable[[str], Any]) -> None:
        self._restore = restore
        self._state = ScopeState()
        self._objects: dict[str, Any] = {}

    @property
    def revision(self) -> int:
        return self._state.revision

    def scope(self) -> dict[str, Any]:
        """A copy of the valid objects, ready for ``Calculator.evaluate``."""
        return dict(self._objects)

    def entry(self, name: str) -> Any | None:
        return self._objects.get(name)

    def sync(self, source: ScopeSnapshot | ScopeDelta | Mapping[str, Any]) -> dict[str, Any]:
        """Apply whichever scope form the request carries and return its objects.

        A plain mapping is the legacy in-process protocol: the caller already
        holds the objects, so the cache becomes that mapping with no revisions.
        """
        if isinstance(source, ScopeSnapshot):
            self.restore(source)
        elif isinstance(source, ScopeDelta):
            self.apply(source)
        else:
            self.replace(source)
        return self.scope()

    def restore(self, snapshot: ScopeSnapshot) -> None:
        """Full recovery (a worker start or a revision gap).

        Every valid entry is restored before either half is replaced, so a
        malformed ``srepr`` cannot leave a half-filled cache.
        """
        objects: dict[str, Any] = {}
        for entry in snapshot.entries:
            if entry.valid:
                objects[entry.name] = self._restore(entry.srepr)
        self._state.reset(snapshot)
        self._objects = objects

    def apply(self, delta: ScopeDelta) -> None:
        """Parse only the entries in ``delta`` and advance the revision.

        Objects and revision are committed together only after both the restore
        and the delta validation succeed.
        """
        objects = dict(self._objects)
        # Reject a stale/gapped/conflicting delta before spending a restore on
        # entries that cannot be committed.
        self._state.check(delta)
        for change in delta.changes:
            entry = change.entry
            if entry is None or not entry.valid:
                objects.pop(change.name, None)
            else:
                objects[change.name] = self._restore(entry.srepr)
        self._state.apply(delta)
        self._objects = objects

    def replace(self, scope: Mapping[str, Any]) -> None:
        """Adopt the legacy request's already-built objects (no revisions)."""
        self._state = ScopeState()
        self._objects = dict(scope)
