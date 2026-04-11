# coding: utf-8
"""Mathematical components based on SymPy and Matplotlib.

This package provides Qt widgets for mathematical visualization, including:
- LaTeXLabel: For rendering LaTeX math expressions as images
- MathPlotWidget: For plotting mathematical expressions
- MathPlotCanvas: Low-level matplotlib canvas
- MathPlotToolbar: Fluent-styled navigation toolbar

All components integrate seamlessly with QFluentWidgets' design language.

Example:
    >>> from app.qfluentplus.components.math import MathPlotWidget, LaTeXLabel
    >>> from sympy import symbols, sin
    >>>
    >>> x = symbols('x')
    >>> plot_widget = MathPlotWidget()
    >>> plot_widget.plot_function(sin(x), (x, -10, 10), title="Sine Wave")
    >>>
    >>> label = LaTeXLabel(r"$\\int_{0}^{\\infty} e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}$")
"""

from .latex_label import LaTeXLabel
from .plot_canvas import MathPlotCanvas
from .plot_toolbar import MathPlotToolbar
from .plot_widget import MathPlotWidget

__all__ = [
    "LaTeXLabel",
    "MathPlotCanvas",
    "MathPlotToolbar",
    "MathPlotWidget",
]
