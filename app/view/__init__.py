# coding: utf-8
"""View layer for the Symplify application.

This package contains all view components following the MVVM pattern.
Views are responsible for UI presentation and user interaction, delegating
business logic to ViewModels.

Example:
    >>> from app.view import MainWindow, CalculatorInterface, VariablesInterface
    >>> window = MainWindow()
"""

from .main_window import MainWindow
from .calculator_interface import CalculatorInterface
from .variables_interface import VariablesInterface

__all__ = [
    "MainWindow",
    "CalculatorInterface",
    "VariablesInterface",
]
