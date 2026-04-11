# coding: utf-8
"""ViewModel layer for the Symplify application.

This package contains all ViewModel components following the MVVM pattern.
ViewModels connect Views with Models and use EventBus for decoupled
communication.

Example:
    >>> from app.viewmodel import CalculatorViewModel, VariablesViewModel
    >>> from app.model import Calculator, VariableManager
    >>> calc_vm = CalculatorViewModel(Calculator(), VariableManager())
    >>> var_vm = VariablesViewModel(VariableManager())
"""

from .calculator_viewmodel import CalculatorViewModel
from .variables_viewmodel import VariablesViewModel
from .main_window_viewmodel import MainWindowViewModel
from .history_viewmodel import HistoryViewModel, HistoryItem
from .log_viewmodel import LogViewModel, LogEntry, LogLevel
from .keyboard_viewmodel import KeyboardViewModel

__all__ = [
    "CalculatorViewModel",
    "VariablesViewModel",
    "MainWindowViewModel",
    "HistoryViewModel",
    "LogViewModel",
    "KeyboardViewModel",
    "HistoryItem",
    "LogEntry",
    "LogLevel",
]
