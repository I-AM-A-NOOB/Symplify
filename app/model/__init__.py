# coding: utf-8
"""Model layer for the Symplify application.

This package contains all business logic and data models,
completely independent of the view layer.

Example:
    >>> from app.model import Calculator, VariableManager
    >>> calc = Calculator()
    >>> vm = VariableManager()
"""

from .calculator import Calculator, CalculationResult, ResultType
from .variable import VariableManager, Variable

__all__ = [
    "Calculator",
    "CalculationResult",
    "ResultType",
    "VariableManager",
    "Variable",
]
