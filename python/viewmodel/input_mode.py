# coding: utf-8
"""Input mode of the calculator page.

UI state, not model state: it says which input row the user is looking at, so it
lives with the viewmodels rather than in the pure calculation layer. The values
are stable integers exposed to QML (0 = CODE, 1 = ASSIGN) so the view can bind
to ``CalculatorViewModel.inputMode`` as its single source of truth for which
input mode is active.
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
