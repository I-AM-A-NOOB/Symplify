# coding: utf-8
"""Input mode enumeration for the calculator."""

from enum import Enum, auto


class InputMode(Enum):
    """Input mode for the calculator.

    Attributes:
        CODE: Code mode - evaluate an expression and return a result.
        ASSIGN: Assignment mode - assign an expression to a variable.
    """

    CODE = auto()
    ASSIGN = auto()
