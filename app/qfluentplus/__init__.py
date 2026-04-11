# coding: utf-8
"""QFluentPlus - Extended Components for QFluentWidgets.

A collection of custom widgets that extend QFluentWidgets with additional
functionality while maintaining the fluent design language.

Example:
    >>> from app.qfluentplus import Splitter, MathPlotWidget, LaTeXLabel
    >>> from PySide6.QtCore import Qt
    >>>
    >>> splitter = Splitter(Qt.Orientation.Horizontal)
    >>> splitter.addWidget(left_panel)
    >>> splitter.addWidget(right_panel)
"""

# Import resource file to register qss files
from .resource import resource

from .components.splitter import Splitter, SplitterHandle
from .components.math import MathPlotWidget, MathPlotCanvas, MathPlotToolbar, LaTeXLabel
from .common.style_sheet import StyleSheet

__version__ = "1.0.0"
__author__ = "Symplify Team"

__all__ = [
    "Splitter",
    "SplitterHandle",
    "MathPlotWidget",
    "MathPlotCanvas",
    "MathPlotToolbar",
    "LaTeXLabel",
    "StyleSheet",
]
