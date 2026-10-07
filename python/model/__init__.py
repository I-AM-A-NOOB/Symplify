# coding: utf-8
"""Model layer for the QML Symplify app.

Pure business logic, no Qt dependency, no view-layer concerns. The calculation
core is ``Calculator``: it owns what an input means, which names resolve and
what counts as a failure, and answers with ``Success`` or ``Failure``.
"""

import sys

from .calculator import (
    AUGMENTED_OPS,
    ASSIGN_OPS,
    Assignment,
    Calculator,
    ErrorKind,
    Failure,
    Result,
    Success,
)
from .latex import render_latex, render_latex_definition
from .variable import (
    VariableEntry,
    VariableManager,
    classify_type,
    is_sympy_name,
    validate_name,
)

# Python caps int -> str at 4300 digits by default: a guard against a DoS from
# *untrusted* input (CVE-2020-10735). The input here is the user's own typing
# (invariant 1), and a calculator has to be able to show the number it just
# computed — `2**100000` evaluates fine, but its 30103 digits raised ValueError
# in the viewmodel's `str(result.value)`, so the app computed an answer it could
# not display and the failure surfaced inside a Qt slot. Raised once, on the
# package every model consumer imports (the viewmodels and the tests alike),
# rather than at each of the four places that stringify a value.
sys.set_int_max_str_digits(0)

__all__ = [
    "AUGMENTED_OPS",
    "ASSIGN_OPS",
    "Assignment",
    "Calculator",
    "ErrorKind",
    "Failure",
    "Result",
    "Success",
    "render_latex",
    "render_latex_definition",
    "VariableEntry",
    "VariableManager",
    "classify_type",
    "is_sympy_name",
    "validate_name",
]
