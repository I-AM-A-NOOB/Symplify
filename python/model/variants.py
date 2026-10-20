# coding: utf-8
"""Other spellings of a value, for the calculator's result card.

The model has already answered with the *simplified* value (see
``calculator._simplified``), so this module asks what can still be said
differently: a decimal approximation (``N()``), an expansion, and a
factorisation. Each candidate is dropped when it spells exactly the answer, and
the polynomial ones are gated by degree — expanding ``(x + 1)**1000`` is not a
card row, it is a hang.

Nothing here is a request: a candidate that raises, is empty, or does not
render is simply not offered. That is the same rule the renderer follows — a
representation problem is never a calculation failure.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

import sympy

from .latex import render_latex

#: Polynomial forms are only offered at or below this total degree. A result is
#: read at a glance; an expansion beyond this is not worth the time it takes.
MAX_POLY_DEGREE = 12

#: Guards for the extra ``simplify`` pass. Results are already simplified, so
#: this candidate exists for the day that changes — and a huge result must not
#: pay for a second, pointless simplification.
_MAX_SIMPLIFY_CHARS = 400
_MAX_SIMPLIFY_OPS = 120

#: Unevaluated forms the card can answer with ``doit()``. These are the objects
#: the parser leaves alone on purpose (an ``Integral`` is *what the user typed*),
#: so the evaluated value is exactly the extra form worth offering.
_DOIT_FORMS = (
    sympy.Integral,
    sympy.Derivative,
    sympy.Sum,
    sympy.Product,
    sympy.Limit,
)


@dataclass(frozen=True)
class Variant:
    """One alternative form of a result.

    Attributes:
        kind: ``'simplify'``, ``'numeric'``, ``'expand'`` or ``'factor'`` — the
            UI translates it; this layer holds no display strings.
        value: The sympy object, for callers that need more than its spelling.
        expression: The plain-text form (what "Copy expression" copies).
        latex: LaTeX source, or ``''`` when sympy cannot typeset it.
    """

    kind: str
    value: Any
    expression: str
    latex: str


def _add(
    out: List[Variant],
    seen: set[str],
    kind: str,
    value: Any,
) -> None:
    """Append ``value`` as ``kind`` unless it spells something already listed."""
    try:
        expression = str(value)
    except Exception:  # noqa: BLE001 - unprintable is just not a candidate
        return
    if not expression or expression in seen:
        return
    seen.add(expression)
    out.append(Variant(kind, value, expression, render_latex(value)))


def _polynomial(value: Any) -> Optional[sympy.Poly]:
    """``value`` as a small polynomial in plain symbols, or None.

    The generator check keeps `sin(x)` and `pi` out: sympy will happily treat
    them as polynomial generators, but their "expansions" are the expression
    itself and the forms are not what this card is for.
    """
    try:
        # `is_polynomial` is a method on Expr (unlike the `is_number` flags).
        if value.is_polynomial() is not True:
            return None
        polynomial = sympy.Poly(value)
    except Exception:  # noqa: BLE001 - not something expand/factor can improve
        return None
    if not polynomial.gens or polynomial.total_degree() > MAX_POLY_DEGREE:
        return None
    if not all(gen.is_Symbol for gen in polynomial.gens):
        return None
    return polynomial


def variants(value: Any) -> Tuple[Variant, ...]:
    """Alternative forms worth showing beside ``value``.

    Only one sympy object qualifies: ``solve``'s list of roots and other
    non-expression answers have no meaningful expansion or factorisation.

    Order is the card's order: the simplified form (when it differs), the
    numeric value, the expansion, the factorisation.
    """
    if not isinstance(value, sympy.Expr):
        return ()

    try:
        base_expression = str(value)
    except Exception:  # noqa: BLE001 - unprintable means nothing to compare
        return ()

    variants_out: List[Variant] = []
    seen = {base_expression}

    # `v.is_Integer` is None for non-numbers; `is True` keeps the check honest.
    try:
        small_enough = (
            len(base_expression) <= _MAX_SIMPLIFY_CHARS
            and value.count_ops() <= _MAX_SIMPLIFY_OPS
        )
    except Exception:  # noqa: BLE001 - count_ops is an optimisation, not a gate
        small_enough = False
    if small_enough:
        try:
            simplified = sympy.simplify(value)
        except Exception:  # noqa: BLE001 - "no simplification" is not a failure
            pass
        else:
            _add(variants_out, seen, "simplify", simplified)

    #: `Integral(...)`, `Derivative(...)`, `Sum`, `Product` and `Limit` are kept
    #: unevaluated by the parser. `doit()` is what they become; a result with no
    #: closed form simply leads to another identical expression and is dropped.
    try:
        needs_doit = bool(value.atoms(*_DOIT_FORMS))
    except Exception:  # noqa: BLE001 - no atoms is no candidate
        needs_doit = False
    if needs_doit:
        try:
            evaluated = value.doit()
        except Exception:  # noqa: BLE001 - an unevaluable form is not a failure
            pass
        else:
            _add(variants_out, seen, "doit", evaluated)

    if (value.is_number is True
            and value.is_Integer is not True
            and not isinstance(value, sympy.Float)):
        try:
            approximate = value.evalf(15)
        except Exception:  # noqa: BLE001 - just not a candidate
            pass
        else:
            _add(variants_out, seen, "numeric", approximate)

    if _polynomial(value) is not None:
        try:
            expanded = sympy.expand(value)
        except Exception:  # noqa: BLE001
            pass
        else:
            _add(variants_out, seen, "expand", expanded)
        try:
            factored = sympy.factor(value)
        except Exception:  # noqa: BLE001
            pass
        else:
            _add(variants_out, seen, "factor", factored)

    return tuple(variants_out)
