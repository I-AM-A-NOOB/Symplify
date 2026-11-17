"""The synchronous, in-process calculation backend (tests/headless only).

This is the test/headless path: it evaluates SymPy on the caller's thread and
emits the same plain-data ``ResultView`` / ``VariantView`` DTOs as the
application's :class:`ProcessBackend`. Keeping this module separate is what lets
the UI package import without loading SymPy; only callers that explicitly ask
for the inline backend pay for it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QObject, Signal

from ..model.calculator import Calculator, Success
from ..model.srepr import restore_srepr
from ..model.variants import variants
from ..plot_programs import with_plot
from ..result_payload import assignment_candidate, result_view, variant_views
from ..scope_cache import ScopeCache
from ..worker_protocol import ParsePolicy, ScopeDelta, ScopeSnapshot


class InlineBackend(QObject):
    """Synchronous backend: evaluate in-process, emit the result immediately.

    No timeout: a runaway request blocks the caller exactly as it did before
    the backend existed. Tests and headless callers use this; the application
    passes a ``ProcessBackend``.
    """

    finished = Signal(int, object)
    variantsReady = Signal(int, object)
    timedOut = Signal(int)
    failed = Signal(int, str)
    #: The user explicitly cancelled the active request. Unlike a timeout this
    #: keeps the previous result and does not write a failure card.
    cancelled = Signal(int)

    timeout_seconds = 0.0
    #: The inline backend never replaces its process; the API matches
    #: ProcessBackend so the scope sender can treat both the same.
    generation = 0

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._calculator = Calculator()
        self._parse_policy = ParsePolicy()
        self._scope = ScopeCache(restore_srepr)

    def set_parse_policy(self, policy: ParsePolicy) -> None:
        """Set the parser policy used by the next in-process evaluation."""
        if not isinstance(policy, ParsePolicy):
            raise TypeError(
                f"parse_policy must be ParsePolicy, got {type(policy).__name__}"
            )
        self._parse_policy = policy

    def warm_up(self) -> None:
        """Nothing to start: the inline backend runs in this process."""

    def submit(
        self,
        request_id: int,
        kind: str,
        payload: Any,
        scope: Mapping[str, Any] | ScopeSnapshot | ScopeDelta,
    ) -> None:
        """Evaluate now and emit the outcome before returning."""
        canonical_input = ""
        try:
            self._calculator.set_parse_policy(self._parse_policy)
            scope_objects = self._scope.sync(scope)
            canonical_source = getattr(payload, "expression", str(payload))
            canonical_input = self._calculator.canonical_input(
                canonical_source, scope_objects
            )
            if kind == "evaluate":
                result = self._calculator.evaluate(payload, scope_objects)
            else:
                result = self._calculator.assign(payload, scope_objects)
        except Exception as exc:  # noqa: BLE001 - a crash is a report, not a raise
            canonical_input = ""
            self.failed.emit(request_id, f"{type(exc).__name__}: {exc}")
        else:
            result = with_plot(result)
            entry = None
            if kind in ("assign", "variable") and isinstance(result, Success):
                try:
                    entry = assignment_candidate(payload.target, result.value)
                except Exception:  # noqa: BLE001 - candidate is optional
                    entry = None
            self.finished.emit(
                request_id,
                result_view(
                    result, request_id,
                    scope_revision=self._scope.revision,
                    profile_id=self._parse_policy.profile_id,
                    entry=entry,
                    canonical_input=canonical_input,
                ),
            )
            variant_rows = ()
            if isinstance(result, Success):
                try:
                    variant_rows = variants(result.value)
                except Exception:  # noqa: BLE001 - no card, not a failed answer
                    variant_rows = ()
            self.variantsReady.emit(request_id, variant_views(variant_rows))

    def cancel(self, *, notify: bool = False) -> None:
        """Nothing to cancel: `submit` has already returned."""

    def shutdown(self) -> None:
        """Nothing to release."""
