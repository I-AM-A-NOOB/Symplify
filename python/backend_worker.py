"""The calculation backend's child process (zero Qt).

A `ProcessBackend` starts this module with ``spawn`` and talks to it over a
pickled duplex pipe. Keeping the loop out of the Qt module is deliberate: the
spawned interpreter must not import PySide6, and this file can be tested without
a GUI.

Protocol (both directions): ``(request_id, ...)``.
- Parent → child: ``(request_id, "evaluate"|"assign"|"variable", payload, scope,
  parse_policy)``; older callers may omit the final field and get the default
  policy. ``"assign"`` and ``"variable"`` both carry an :class:`Assignment`;
  ``"variable"`` is the Variables page's write and deliberately skips the
  optional variant rows, because it has no cards to show. ``None`` asks the
  worker to exit. ``scope`` is either the legacy mapping of already-built SymPy
  objects, a :class:`~python.worker_protocol.ScopeSnapshot`, or a
  :class:`~python.worker_protocol.ScopeDelta`; ``parse_policy`` is a validated
  :class:`~python.worker_protocol.ParsePolicy`.
- Child → parent: ``(request_id, "result", ResultView, ())`` followed by
  ``(request_id, "variants", None, tuple[VariantView, ...])`` for
  ``evaluate``/``assign``. The result is sent first so the UI can display it
  immediately; the variants are the display rows for a success (empty for a
  failure), because `doit()` and the polynomial forms are symbolic work too and
  remain inside the request's deadline. ``variable`` sends the result only.
  No SymPy object crosses this pipe: the worker converts at the boundary with
  :func:`python.result_payload.result_view`.

The worker is disposable: the parent terminates it at its deadline. Its
:class:`~python.scope_cache.ScopeCache` is a performance cache, not authority.
A legacy mapping replaces it; a snapshot parses every entry once (the path after
a restart); a delta parses only the changed entries. A Store snapshot or delta
whose revision does not line up is refused, so a lost worker always recovers
from a fresh snapshot rather than a guessed scope.
"""

from typing import Any

from .model.calculator import Assignment, Calculator, ErrorKind, Failure, Success
from .model.srepr import restore_srepr
from .model.variants import variants
from .plot_programs import with_plot
from .result_payload import assignment_candidate, result_view, variant_views
from .sandbox import apply_worker_limits
from .scope_cache import ScopeCache


def _assignment_entry(kind: str, payload: Any, result: Any) -> Any:
    """The Store candidate for an assignment, or None for a read/failure."""
    if kind not in ("assign", "variable") or not isinstance(result, Success):
        return None
    try:
        return assignment_candidate(payload.target, result.value)
    except Exception:  # noqa: BLE001 - a candidate is optional extra data
        return None


def worker_main(connection: Any) -> None:
    """Serve calculation requests until the parent closes the pipe.

    Every failure is converted to a ``Failure`` for the parent: an exception
    escaping this loop would look like a backend crash, which is a different
    report and a different recovery.
    """
    # Apply the child-side half of the sandbox before the first request. On
    # Windows the Job Object is assigned by the parent; on POSIX this sets the
    # process's resource limits and sheds the environment.
    apply_worker_limits()
    calculator = Calculator()
    scope_cache = ScopeCache(restore_srepr)
    try:
        while True:
            try:
                request = connection.recv()
            except (EOFError, OSError):
                return
            if request is None:
                return

            if len(request) == 5:
                request_id, kind, payload, scope, parse_policy = request
            else:
                # Older 4-field requests (tests, one-off callers) use the
                # calculator's default policy.
                request_id, kind, payload, scope = request
                parse_policy = None
            try:
                if parse_policy is not None:
                    calculator.set_parse_policy(parse_policy)
                profile_id = calculator.parse_policy.profile_id
                # ``scope`` is either the legacy mapping of SymPy objects or a
                # Store ScopeSnapshot/ScopeDelta. The cache parses only what the
                # revision says changed; a bad sync is reported like any other
                # internal failure and leaves the cache untouched.
                scope_objects = scope_cache.sync(scope)
                canonical_source = (
                    payload.expression
                    if isinstance(payload, Assignment)
                    else str(payload)
                )
                canonical_input = calculator.canonical_input(
                    canonical_source, scope_objects
                )
                if kind == "evaluate":
                    result = calculator.evaluate(payload, scope_objects)
                else:
                    result = calculator.assign(payload, scope_objects)
            except Exception as exc:  # noqa: BLE001 - report, never escape
                canonical_input = ""
                expression = (
                    payload.expression
                    if isinstance(payload, Assignment)
                    else str(payload)
                )
                result = Failure(
                    expression,
                    ErrorKind.INTERNAL,
                    f"{type(exc).__name__}: {exc}",
                )
            if kind == "variable":
                # The Variables page has no variant cards: send the result
                # only, so the dedicated worker can serve the next queued write
                # without computing/delaying optional forms.
                candidate = _assignment_entry(kind, payload, result)
                view = result_view(
                    result, request_id, scope_revision=scope_cache.revision,
                    profile_id=profile_id, entry=candidate,
                    canonical_input=canonical_input,
                )
                try:
                    connection.send((request_id, "result", view, ()))
                except (BrokenPipeError, EOFError, OSError):
                    return
                continue
            # The answer goes out before the optional forms. SymPy's `doit`,
            # `expand` and `factor` can be the slowest part of a request, but
            # they are not needed to display the result.
            result = with_plot(result)
            candidate = _assignment_entry(kind, payload, result)
            view = result_view(
                result, request_id, scope_revision=scope_cache.revision,
                profile_id=profile_id, entry=candidate,
                canonical_input=canonical_input,
            )
            try:
                connection.send((request_id, "result", view, ()))
            except (BrokenPipeError, EOFError, OSError):
                return
            variant_rows = ()
            if isinstance(result, Success):
                try:
                    variant_rows = variants(result.value)
                except Exception:  # noqa: BLE001 - no card, no failure
                    variant_rows = ()
            try:
                # Variants remain part of the symbolic work and stay under the
                # request's deadline; the parent only renders their LaTeX.
                connection.send(
                    (request_id, "variants", None, variant_views(variant_rows))
                )
            except (BrokenPipeError, EOFError, OSError):
                return
    finally:
        try:
            connection.close()
        except OSError:
            pass
