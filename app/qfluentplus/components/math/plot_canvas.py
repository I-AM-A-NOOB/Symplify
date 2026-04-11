# coding: utf-8
"""Fluent-styled matplotlib canvas component.

This module provides MathPlotCanvas, a FigureCanvas with Fluent Design
theme support. It is a pure UI component with no mathematical computation.

Use standard matplotlib API for plotting:
    >>> canvas.axes.plot(x, y, label="data")
    >>> canvas.axes.set_title("My Plot")
    >>> canvas.draw()

Example:
    >>> from app.qfluentplus.components.math.plot_canvas import MathPlotCanvas
    >>> import numpy as np
    >>> canvas = MathPlotCanvas()
    >>> x = np.linspace(-5, 5, 500)
    >>> y = np.sin(x)
    >>> canvas.axes.plot(x, y, label="sin(x)")
    >>> canvas.axes.legend()
    >>> canvas.draw()
"""
from typing import Optional

from PySide6.QtWidgets import QWidget

import matplotlib

matplotlib.use("QtCairo")
from matplotlib.backends.backend_qtcairo import FigureCanvasQTCairo as FigureCanvas
from matplotlib.figure import Figure

from qfluentwidgets import isDarkTheme


class MathPlotCanvas(FigureCanvas):
    """Fluent-styled FigureCanvas.

        A FigureCanvas subclass that automatically applies Fluent Design
    theme colors (light/dark) to matplotlib plots. Provides no additional
    plotting functionality - use standard matplotlib API via self.axes.

        Attributes:
            fig (Figure): The matplotlib figure instance.
            axes (Axes): The primary axes for 2D plotting.
            axes_3d (Axes): The axes for 3D plotting (created on demand).

        Example:
            >>> canvas = MathPlotCanvas()
            >>> canvas.axes.plot([1, 2, 3], [1, 4, 9])
            >>> canvas.axes.set_title("Parabola")
            >>> canvas.draw()
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        width: int = 5,
        height: int = 4,
        dpi: int = 100,
    ):
        """Initialize the canvas with Fluent styling.

        Args:
            parent: The parent widget. Defaults to None.
            width: Figure width in inches. Defaults to 5.
            height: Figure height in inches. Defaults to 4.
            dpi: Dots per inch. Defaults to 100.
        """
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        self.axes_3d = None

        super().__init__(self.fig)
        self.setParent(parent)

        self._setup_style()

    def _setup_style(self):
        """Apply Fluent theme colors to matplotlib."""
        if isDarkTheme():
            self._apply_dark_theme()
        else:
            self._apply_light_theme()

    def _apply_light_theme(self):
        """Apply light theme colors."""
        self.fig.patch.set_facecolor("#ffffff")
        self.axes.set_facecolor("#ffffff")
        self.axes.tick_params(colors="#333333")
        self.axes.xaxis.label.set_color("#333333")
        self.axes.yaxis.label.set_color("#333333")
        self.axes.title.set_color("#333333")
        self.axes.spines["bottom"].set_color("#cccccc")
        self.axes.spines["top"].set_color("#cccccc")
        self.axes.spines["left"].set_color("#cccccc")
        self.axes.spines["right"].set_color("#cccccc")

    def _apply_dark_theme(self):
        """Apply dark theme colors."""
        self.fig.patch.set_facecolor("#2b2b2b")
        self.axes.set_facecolor("#2b2b2b")
        self.axes.tick_params(colors="#cccccc")
        self.axes.xaxis.label.set_color("#cccccc")
        self.axes.yaxis.label.set_color("#cccccc")
        self.axes.title.set_color("#cccccc")
        self.axes.spines["bottom"].set_color("#555555")
        self.axes.spines["top"].set_color("#555555")
        self.axes.spines["left"].set_color("#555555")
        self.axes.spines["right"].set_color("#555555")

    def clear(self):
        """Clear the axes and reapply theme."""
        self.axes.clear()
        self._setup_style()
        self.draw()

    def update_theme(self):
        """Update theme when system theme changes."""
        self._setup_style()
        self.draw()
