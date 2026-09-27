# coding: utf-8
"""How a value is spelled in TeX.

Two steps put a formula on screen, and this is the first: **value → TeX source**,
through sympy's printer. The second, **TeX source → SVG**, is
``python/latex_render.py`` (ziamath). Neither imports Qt, and neither knows about
the other.

Both live here rather than beside the evaluation they serve because this is a
*representation* concern, not a calculation one: ``Calculator`` owns what an
input means and what counts as a failure, and it is the one that answers with a
value and its TeX spelling together. The definition line below has a second
caller already (the Variables table's `name = value`), so this is the model
layer's public surface, not the calculator's private detail.

The failure contract is the reason to keep them together: a value sympy cannot
typeset is **not** a calculation failure, so these answer with an empty string
instead of raising, and the surfaces that show artwork read "" as "there is
nothing to draw" and fall back to plain text.
"""

from typing import Any

from sympy import Symbol, latex


def render_latex(value: Any) -> str:
    """LaTeX for ``value``, or ``''`` when sympy cannot render it.

    Deliberately outside the evaluation path: a rendering problem must never be
    reported as a calculation failure.
    """
    try:
        return latex(value)
    except Exception:
        return ""


def render_latex_definition(name: str, value: Any) -> str:
    """LaTeX for ``name = value``, with the name typeset as a symbol.

    sympy's naming is the point: ``alpha``, ``rho`` and friends have their own
    TeX forms, so the name goes through ``Symbol`` and comes out the way the
    value's own LaTeX spells them. A value sympy cannot render takes the whole
    line with it — there is nothing to print beside an empty right-hand side.
    """
    rendered = render_latex(value)
    if not rendered:
        return ""
    try:
        return f"{latex(Symbol(name))} = {rendered}"
    except Exception:                  # a name sympy refuses to read as a symbol
        return ""
