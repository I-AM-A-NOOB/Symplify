"""Convert model results into the plain-data DTOs that cross to the UI.

This module is the only bridge from ``Success | Failure`` / ``Variant`` to
:class:`ResultView` / :class:`VariantView` / :class:`PlotSpec`. It runs in the
Compute worker (or the inline test backend), never in the UI: the UI receives
strings and qmlmathplot's plain Program dicts only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import sympy

from .model.calculator import Result, Success
from .model.latex import render_latex_definition
from .model.variable import classify_type, reserved_name_warning
from .model.variants import Variant
from .worker_protocol import PlotSpec, ResultView, StoreEntryCandidate, VariantView


def assignment_candidate(name: str, value: Any) -> StoreEntryCandidate:
    """The Store-shaped candidate for one assigned value (worker-side only)."""
    return StoreEntryCandidate(
        name=name,
        srepr=sympy.srepr(value),
        display=str(value),
        type_label=classify_type(value),
        latex=render_latex_definition(name, value),
        warning=reserved_name_warning(name) or "",
        valid=True,
    )


def result_view(
    result: Result,
    request_id: int,
    *,
    scope_revision: int = 0,
    profile_id: str = "default",
    entry: StoreEntryCandidate | None = None,
    canonical_input: str = "",
) -> ResultView:
    """One result as the UI-facing DTO (no SymPy object)."""
    if isinstance(result, Success):
        return ResultView(
            request_id=request_id,
            expression=result.expression,
            text=str(result.value),
            latex=result.latex,
            is_error=False,
            error_message="",
            hint="",
            variants=(),
            plot=_plot_specs(result.plot),
            scope_revision=scope_revision,
            profile_id=profile_id,
            entry=entry,
            canonical_input=canonical_input,
        )
    return ResultView(
        request_id=request_id,
        expression=result.expression,
        text="",
        latex="",
        is_error=True,
        error_message=result.message,
        hint=result.hint,
        variants=(),
        plot=(),
        scope_revision=scope_revision,
        profile_id=profile_id,
        error_kind=result.kind.name,
        canonical_input=canonical_input,
    )


def variant_views(rows: Iterable[Variant]) -> tuple[VariantView, ...]:
    """The alternative rows as display data."""
    return tuple(
        VariantView(kind=row.kind, expression=row.expression, latex=row.latex)
        for row in rows
    )


def _plot_specs(plot: Iterable[Mapping[str, Any]]) -> tuple[PlotSpec, ...]:
    specs = []
    for spec in plot:
        program = spec.get("program")
        to_dict = getattr(program, "to_dict", None)
        if callable(to_dict):
            data = to_dict()
        elif isinstance(program, Mapping):
            data = dict(program)
        else:
            continue
        specs.append(
            PlotSpec(
                label=str(spec.get("label", "")),
                role=str(spec.get("role", "result")),
                program=data,
            )
        )
    return tuple(specs)
