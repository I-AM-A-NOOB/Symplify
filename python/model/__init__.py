# coding: utf-8
"""Model layer for the QML Symplify app.

Pure business logic, no Qt dependency, no view-layer concerns. The calculation
core is ``Calculator``: it owns what an input means, which names resolve and
what counts as a failure, and answers with ``Success`` or ``Failure``.
"""

from .calculator import (
    AUGMENTED_OPS,
    ASSIGN_OPS,
    Assignment,
    Calculator,
    ErrorKind,
    Failure,
    Result,
    Success,
    render_latex,
)
from .variable import (
    VariableEntry,
    VariableManager,
    classify_type,
    is_sympy_name,
    validate_name,
)

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
    "VariableEntry",
    "VariableManager",
    "classify_type",
    "is_sympy_name",
    "validate_name",
]
