# coding: utf-8
"""Input mode enumeration for the calculator.

This module defines the input modes for calculator operations.
Placed in common layer to allow access from both View and ViewModel.

Example:
    >>> from app.common.input_mode import InputMode
    >>> mode = InputMode.CODE
"""
from enum import Enum, auto


class InputMode(Enum):
    """Input mode for the calculator.

    Attributes:
        CODE: Code mode - evaluate expression and return result.
        ASSIGN: Assignment mode - assign expression to a variable.
    """

    CODE = auto()
    ASSIGN = auto()
