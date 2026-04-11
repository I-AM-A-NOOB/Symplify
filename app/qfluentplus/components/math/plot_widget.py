# coding: utf-8
"""Fluent-styled plotting widget component.

This module provides MathPlotWidget, a complete plotting widget with
canvas and toolbar. It is a pure UI component with no mathematical
computation - use standard matplotlib API via self.canvas.axes.

Example:
    >>> from app.qfluentplus.components.math.plot_widget import MathPlotWidget
    >>> import numpy as np
    >>>
    >>> widget = MathPlotWidget()
    >>> x = np.linspace(-5, 5, 500)
    >>> y = np.sin(x)
    >>> widget.canvas.axes.plot(x, y, label="sin(x)")
    >>> widget.canvas.axes.legend()
    >>> widget.canvas.draw()
"""
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout

from matplotlib.figure import Figure
from matplotlib.axes import Axes
from qfluentwidgets import qconfig

from .plot_canvas import MathPlotCanvas
from .plot_toolbar import MathPlotToolbar
from ...common.style_sheet import StyleSheet


class MathPlotWidget(QWidget):
    """Fluent-styled plotting widget.

    A complete plotting widget combining canvas and toolbar.
    Provides no plotting functionality - use standard matplotlib
    API via self.canvas.axes for all plotting operations.

    Attributes:
        canvas (MathPlotCanvas): The matplotlib canvas for plotting.
        toolbar (MathPlotToolbar): The Fluent-styled navigation toolbar.

    Signals:
        plotClicked: Emitted when the plot area is clicked.

    Example:
        >>> widget = MathPlotWidget()
        >>> widget.canvas.axes.plot([1, 2, 3], [1, 4, 9])
        >>> widget.canvas.axes.set_title("Parabola")
        >>> widget.canvas.draw()
    """

    plotClicked = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        width: int = 5,
        height: int = 4,
        dpi: int = 100,
        show_toolbar: bool = True,
    ):
        """Initialize the plot widget.

        Args:
            parent: The parent widget. Defaults to None.
            width: Figure width in inches. Defaults to 5.
            height: Figure height in inches. Defaults to 4.
            dpi: Dots per inch. Defaults to 100.
            show_toolbar: Whether to show navigation toolbar. Defaults to True.
        """
        super().__init__(parent)

        self._setup_ui(width, height, dpi, show_toolbar)
        self._apply_style()
        self._connect_signals()

    def _setup_ui(self, width: int, height: int, dpi: int, show_toolbar: bool):
        """Set up the user interface.

        Args:
            width: Figure width in inches.
            height: Figure height in inches.
            dpi: Dots per inch.
            show_toolbar: Whether to show toolbar.
        """
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Create canvas
        self.canvas = MathPlotCanvas(self, width, height, dpi)
        self.layout.addWidget(self.canvas)

        # Create Fluent-styled toolbar
        if show_toolbar:
            self.toolbar = MathPlotToolbar(self.canvas, self)
            self.layout.addWidget(self.toolbar)

    def _apply_style(self):
        """Apply QFluentPlus style sheet."""
        StyleSheet.PLOT_WIDGET.apply(self)
        if hasattr(self, "toolbar"):
            StyleSheet.PLOT_TOOLBAR.apply(self.toolbar)

    def _connect_signals(self):
        """Connect signals including theme change."""
        qconfig.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme):
        """Handle theme change.

        Args:
            theme: The new theme.
        """
        self.canvas.update_theme()

    def get_figure(self) -> Figure:
        """Get the matplotlib figure for advanced customization.

        Returns:
            The matplotlib Figure instance.
        """
        return self.canvas.fig

    def get_axes(self) -> Axes:
        """Get the matplotlib axes for advanced customization.

        Returns:
            The matplotlib Axes instance.
        """
        return self.canvas.axes
