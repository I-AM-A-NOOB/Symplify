# coding: utf-8
"""What a result should be drawn as (pure Python, zero Qt).

The plot itself lives in ``qmlmathplot`` and the viewmodel owns it; this module
owns the *decision* — which curves a request produces, what they are called, and
whether one is an implicit level set — so it can be tested without a window.

**Detection is by value, never by text.** A result is plottable when it is a
sympy expression whose free symbols are a subset of :data:`PLOT_SYMBOLS`:
``x**2`` is ``y = x**2``, ``x + y`` is the level set ``x + y = 0``, and ``a*x``
with an unbound ``a`` is not drawn at all — qmlmathplot refuses it, and guessing
parameter values would invent a meaning. Whether the user's *text* mentions ``x``
is irrelevant: ``x = 2`` is the number 2. This is the same test qmlmathplot's
``curve_for`` makes; making it here keeps the decision testable and keeps a
refusal out of a Qt slot.

**The source of a transformation is recorded, not re-parsed.** ``diff(f, x)``
alone cannot say what ``f`` was, and this repository deliberately has no
expression parser (the model has a tokenizer, see `.Agent/DEVELOPER_GUIDE.md`).
So ``Calculator`` shadows the transforming callables while the real parser runs
and notes the calls it made; an ``Origin`` is the outermost of those calls.
:func:`plot_series` then decides what that means: a derivative shows the function
it came from *and* the derivative, a solution shows the expression that was
solved, and everything else shows its result.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import sympy as sp

#: The only names a plotted expression may leave free. ``x`` is the abscissa;
#: ``y`` turns the result into the level set ``F(x, y) = 0`` (which is what a
#: result *is* — an expression, not an equation).
PLOT_SYMBOLS = ("x", "y")

#: The same ceiling the LaTeX renderer applies (``latex_render.MAX_LATEX_CHARS``),
#: for the same reason: the expression becomes generated text (GLSL and LaTeX
#: alike), and a hundred-term result should not spend a shader bake on a plot
#: nobody can read.
MAX_PLOT_EXPR_CHARS = 1000

#: The names above, as sympy compares them.
_SYMBOLS = frozenset(sp.Symbol(name) for name in PLOT_SYMBOLS)

#: Calls whose result is a *different function* of x: the plot shows the
#: argument they were applied to beside the result.
ORIGIN_AND_RESULT = frozenset({"diff", "Derivative", "integrate", "Integral"})

#: Calls whose result is not a curve at all (roots, solution sets, numbers): the
#: plot shows the expression they were applied to, and nothing else. This is the
#: whole of "solve(f, x) plots f".
ORIGIN_ONLY = frozenset({
    "solve", "solveset", "roots", "linsolve", "nonlinsolve", "nsolve",
})

#: Unevaluated symbolic objects no numeric plotter can draw. `Integral`, in
#: particular, has no GLSL spelling; handing it to the printer is the
#: `PrintMethodNotImplementedError` the card used to show. The plot is a
#: *numeric* surface, so it skips these rather than evaluating them — the result
#: card's `doit` variant is where the evaluated form appears.
_UNDRAWABLE_FORMS = (
    sp.Integral,
    sp.Derivative,
    sp.Sum,
    sp.Product,
    sp.Limit,
)

#: What a derived curve is called. The source is always ``f``; these name the
#: derivative/integral so the legend can tell them apart.
RESULT_LABELS = {
    "diff": "f′",
    "Derivative": "f′",
    "integrate": "∫ f dx",
    "Integral": "∫ f dx",
}


def plot_variables() -> Dict[str, Any]:
    """The variables a fresh app starts with: ``x`` and ``y`` as themselves.

    They are ordinary entries in the variables table (not hidden): they make the
    two plotting names visible and editable, and an expression may use them
    without defining anything. Editing one warns (see ``VariablesViewModel``) —
    the value is still stored, exactly like a SymPy built-in.
    """
    return {name: sp.Symbol(name) for name in PLOT_SYMBOLS}


def is_plot_variable(name: str) -> bool:
    """True when ``name`` is one of the names a plot reads."""
    return name in PLOT_SYMBOLS


def plot_variable_warning(name: str) -> str:
    """The dialog's sentence when a plotting variable is changed.

    The write is allowed — the same permissive choice the SymPy built-in warning
    makes, in the same tone — so the sentence is all there is to say.
    """
    return f"{name} is a plotting variable. You asked for it."


@dataclass(frozen=True)
class Origin:
    """The transforming call a request *was*, as the calculator recorded it.

    Attributes:
        call: The function's name (``diff``, ``solve``, …).
        argument: Its first argument, already evaluated — the expression the
            result came from.
    """

    call: str
    argument: Any


@dataclass(frozen=True)
class Series:
    """One curve to draw.

    Attributes:
        expression: The sympy expression (an ``Eq`` is normalized to ``lhs - rhs``).
        label: What the legend calls it.
        implicit: True for the level set ``expression = 0``, False for
            ``y = expression``.
        role: ``"result"`` for the answer itself, ``"source"`` for the expression
            it was derived from.
    """

    expression: Any
    label: str
    implicit: bool = False
    role: str = "result"


def plot_series(value: Any, origin: Optional[Origin] = None) -> Tuple[Series, ...]:
    """The curves to draw for one result, in draw order.

    ``origin`` is ``Success.origin`` — the model's record of the transform call
    the request was, when the request *was* one.
    """
    if origin is not None and origin.call in ORIGIN_ONLY:
        # A solution's roots are not a function of x; the equation that was
        # solved is what a plot can show.
        source = _series(origin.argument, "f", "source")
        return (source,) if source is not None else ()

    series = []
    if origin is not None and origin.call in ORIGIN_AND_RESULT:
        source = _series(origin.argument, "f", "source")
        if source is not None:
            series.append(source)
    label = RESULT_LABELS.get(origin.call, "") if origin is not None else ""
    result = _series(value, label, "result")
    # `diff(f, x)` on an already-linear f answers f itself: one curve, not two
    # identical ones on top of each other.
    if result is not None and not any(item.expression == result.expression for item in series):
        series.append(result)
    return tuple(series)


def _series(value: Any, label: str, role: str) -> Optional[Series]:
    """``value`` as a :class:`Series`, or None when it cannot be drawn."""
    expression = value
    implicit = False
    if isinstance(expression, sp.Eq):
        expression = expression.lhs - expression.rhs
        implicit = True
        label = label or f"{value.lhs} = {value.rhs}"
    if not isinstance(expression, sp.Expr):
        return None
    try:
        if expression.atoms(*_UNDRAWABLE_FORMS):
            return None
    except Exception:  # noqa: BLE001 - an exotic object is not plottable either
        return None
    symbols = expression.free_symbols
    # An empty set is a constant: there is nothing to plot against x, which is
    # also why `oo`/`zoo`/`nan` never reach a shader.
    if not symbols or not symbols <= _SYMBOLS:
        return None
    if len(str(expression)) > MAX_PLOT_EXPR_CHARS:
        return None
    if sp.Symbol("y") in symbols:
        implicit = True
    if not label:
        label = f"{expression} = 0" if implicit else str(expression)
    return Series(expression, label, implicit, role)
