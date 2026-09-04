# coding: utf-8
"""Input mode enumeration for the calculator.

The values are stable integers exposed to QML (0 = CODE, 1 = ASSIGN) so the
view can bind to ``CalculatorViewModel.inputMode`` as its single source of
truth for which input mode is active.
"""

from enum import Enum


class InputMode(Enum):
    """Input mode for the calculator.

    Attributes:
        CODE: Code mode - evaluate an expression and return a result.
        ASSIGN: Assignment mode - assign an expression to a variable.
    """

    CODE = 0
    ASSIGN = 1
