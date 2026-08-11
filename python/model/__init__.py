# coding: utf-8
"""Model layer for the QML Symplify app.

Pure business logic, no Qt dependency, no view-layer concerns.
This is a pruned port of the widgets app's ``app/model`` tree:
the matplotlib plotting slice (``PlotData``/``PlotDataPoints``/``PlotModel``)
and other dead code are intentionally not carried over.
"""

from .calculator import Calculator, CalculationResult, ResultType
from .input_mode import InputMode
from .variable import VariableManager

__all__ = [
    "Calculator",
    "CalculationResult",
    "ResultType",
    "InputMode",
    "VariableManager",
]
