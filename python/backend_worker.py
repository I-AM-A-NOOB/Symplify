# coding: utf-8
"""The calculation backend's child process (zero Qt).

A `ProcessBackend` starts this module with ``spawn`` and talks to it over a
pickled duplex pipe. Keeping the loop out of the Qt module is deliberate: the
spawned interpreter must not import PySide6, and this file can be tested without
a GUI.

Protocol (both directions): ``(request_id, ...)``.
- Parent → child: ``(request_id, "evaluate"|"assign", payload, scope)``; payload
  is the expression text or an :class:`Assignment`. ``None`` asks the worker to
  exit.
- Child → parent: ``(request_id, Success | Failure, variants)``; ``variants`` is
  the `model.variants` tuple for a success (empty for a failure), because
  `doit()` and the polynomial forms are symbolic work too and belong inside the
  timeout.

The worker is disposable: the parent terminates it at its deadline. That is why
a single ``Calculator`` can be reused between requests — nothing here holds the
user's variables, which arrive with every request.
"""

from typing import Any

from .model.calculator import Assignment, Calculator, ErrorKind, Failure, Success
from .model.variants import variants


def worker_main(connection: Any) -> None:
    """Serve calculation requests until the parent closes the pipe.

    Every failure is converted to a ``Failure`` for the parent: an exception
    escaping this loop would look like a backend crash, which is a different
    report and a different recovery.
    """
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
            # Variants are part of the symbolic work (they may call `doit()`,
            # `expand`, `factor`). Computing them here puts that work under the
            # same deadline as the answer; the UI only renders their LaTeX.
            variant_rows = ()
            if isinstance(result, Success):
                try:
                    variant_rows = variants(result.value)
                except Exception:  # noqa: BLE001 - no variant card, no failure
                    variant_rows = ()
            try:
                connection.send((request_id, result, variant_rows))
            except (BrokenPipeError, EOFError, OSError):
                return
    finally:
        try:
            connection.close()
        except OSError:
            pass
