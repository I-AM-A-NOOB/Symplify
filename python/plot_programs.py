"""Attach qmlmathplot display programs to a calculation result.

The worker owns this step: it already has SymPy, so it can decide which curves
the result produces and print them to qmlmathplot's plain :class:`Program`
(GLSL plus ``math``/``numpy`` sources). The UI then only injects programs into
the plot; it never imports SymPy or qmlmathplot's calculator side.

``with_plot`` is shared with ``InlineBackend`` so tests and headless callers see
the same plot payload as the spawned worker.
"""

from dataclasses import replace

from .model.calculator import Success


def with_plot(result: object) -> object:
    """``result`` with its plain plot specs attached (a Success only)."""
    if not isinstance(result, Success):
        return result
    from qmlmathplot.calc import build_program

    from .model.plotting import plot_series

    specs = []
    for series in plot_series(result.value, result.origin):
        try:
            program = build_program(str(series.expression), implicit=series.implicit)
        except Exception:  # noqa: BLE001 - nothing to draw is not a failure
            continue
        if program.error:
            continue
        specs.append({
            "program": program,
            "label": series.label,
            "role": series.role,
        })
    return replace(result, plot=tuple(specs))
