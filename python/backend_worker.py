"""The calculation backend's child process (zero Qt).

A `ProcessBackend` starts this module with ``spawn`` and talks to it over a
pickled duplex pipe. Keeping the loop out of the Qt module is deliberate: the
spawned interpreter must not import PySide6, and this file can be tested without
a GUI.

Protocol (both directions): ``(request_id, ...)``.
- Parent → child: ``(request_id, "evaluate"|"assign", payload, scope)``; payload
  is the expression text or an :class:`Assignment`. ``None`` asks the worker to
  exit.
- Child → parent: ``(request_id, "result", Success | Failure, ())`` followed by
  ``(request_id, "variants", None, variants)``. The result is sent first so the
  UI can display it immediately; the variants are the `model.variants` tuple for
  a success (empty for a failure), because `doit()` and the polynomial forms are
  symbolic work too and remain inside the request's deadline.

The worker is disposable: the parent terminates it at its deadline. That is why
a single ``Calculator`` can be reused between requests — nothing here holds the
user's variables, which arrive with every request.
"""

from typing import Any

from .model.calculator import Assignment, Calculator, ErrorKind, Failure, Success
from .model.variants import variants
from .sandbox import apply_worker_limits


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
    try:
        while True:
            try:
                request = connection.recv()
            except (EOFError, OSError):
                return
            if request is None:
                return

            request_id, kind, payload, scope = request
            try:
                if kind == "evaluate":
                    result = calculator.evaluate(payload, scope)
                else:
                    result = calculator.assign(payload, scope)
            except Exception as exc:  # noqa: BLE001 - report, never escape
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
            # The answer goes out before the optional forms. SymPy's `doit`,
            # `expand` and `factor` can be the slowest part of a request, but
            # they are not needed to display the result.
            try:
                connection.send((request_id, "result", result, ()))
                # Variants remain part of the symbolic work and stay under the
                # request's deadline; the parent only renders their LaTeX.
                variant_rows = ()
                if isinstance(result, Success):
                    try:
                        variant_rows = variants(result.value)
                    except Exception:  # noqa: BLE001 - no card, no failure
                        variant_rows = ()
                connection.send(
                    (request_id, "variants", None, variant_rows)
                )
            except (BrokenPipeError, EOFError, OSError):
                return
    finally:
        try:
            connection.close()
        except OSError:
            pass
