# coding: utf-8
"""LaTeX rendering label component.

This module provides LaTeXLabel, a QLabel that renders LaTeX mathematical
expressions as images using Matplotlib's mathtext.

Example:
    >>> from app.qfluentplus.components.math.latex_label import LaTeXLabel
    >>> label = LaTeXLabel(r"$\int_{0}^{\infty} e^{-x^2} dx = \frac{\sqrt{\pi}}{2}$")
    >>> label.setFontSize(16)
"""
from typing import Optional
from io import BytesIO

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtGui import QPixmap, QImage

from matplotlib.figure import Figure
from qfluentwidgets import isDarkTheme


class LaTeXLabel(QLabel):
    """A QLabel that renders LaTeX mathematical expressions.

    Uses Matplotlib's mathtext to render LaTeX expressions as images.
    Supports both light and dark themes with automatic color adaptation.

    Attributes:
        text (str): The LaTeX expression to render.
        dpi (int): Resolution of the rendered image.
        font_size (int): Font size for the LaTeX expression.

    Example:
        >>> label = LaTeXLabel(r"$\\int_{0}^{\\infty} e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}$")
        >>> label.setFontSize(16)
        >>> label.updateTheme()
    """

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        font_size: int = 12,
        dpi: int = 150,
    ):
        """Initialize the LaTeX label.

        Args:
            text: The LaTeX expression to render. Defaults to empty string.
            parent: The parent widget. Defaults to None.
            font_size: Font size for the LaTeX expression. Defaults to 12.
            dpi: Resolution of the rendered image. Defaults to 150.
        """
        super().__init__(parent)
        self._latex_text = text
        self._font_size = font_size
        self._dpi = dpi
        self._padding = 10

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._render_latex()

    def setText(self, text: str):
        """Set the LaTeX expression to render.

        Args:
            text: The LaTeX expression string.
        """
        self._latex_text = text
        self._render_latex()

    def text(self) -> str:
        """Get the current LaTeX expression.

        Returns:
            The current LaTeX expression string.
        """
        return self._latex_text

    def setFontSize(self, size: int):
        """Set the font size for the LaTeX expression.

        Args:
            size: Font size in points.
        """
        self._font_size = size
        self._render_latex()

    def fontSize(self) -> int:
        """Get the current font size.

        Returns:
            The font size in points.
        """
        return self._font_size

    def setDpi(self, dpi: int):
        """Set the resolution for rendering.

        Args:
            dpi: Dots per inch.
        """
        self._dpi = dpi
        self._render_latex()

    def dpi(self) -> int:
        """Get the current resolution.

        Returns:
            The DPI value.
        """
        return self._dpi

    def _get_text_color(self) -> str:
        """Get the text color based on current theme.

        Returns:
            Hex color string for the text.
        """
        if isDarkTheme():
            return "#cccccc"
        return "#333333"

    def _render_latex(self):
        """Render the LaTeX expression to a QPixmap."""
        if not self._latex_text:
            self.setPixmap(QPixmap())
            return

        try:
            # Create a figure with transparent background
            fig = Figure(figsize=(4, 0.5), dpi=self._dpi)
            fig.patch.set_alpha(0)

            # Add text
            ax = fig.add_subplot(111)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            ax.set_facecolor("none")

            text_color = self._get_text_color()

            # Render LaTeX text using matplotlib's mathtext
            # Wrap in $ if not already wrapped
            latex_text = self._latex_text
            if not latex_text.startswith("$"):
                latex_text = f"${latex_text}$"

            ax.text(
                0.5,
                0.5,
                latex_text,
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=self._font_size,
                color=text_color,
                transform=ax.transAxes,
                usetex=False,  # Use matplotlib's mathtext, not external LaTeX
            )

            # Save to buffer
            buf = BytesIO()
            fig.savefig(
                buf,
                format="png",
                dpi=self._dpi,
                bbox_inches="tight",
                pad_inches=0.1,
                transparent=True,
            )
            buf.seek(0)

            # Convert to QPixmap
            image = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(image)

            self.setPixmap(pixmap)

            # Clean up
            import matplotlib.pyplot as plt

            plt.close(fig)

        except Exception as e:
            # If rendering fails, show error text
            self.setText(f"[LaTeX Error: {str(e)}]")

    def updateTheme(self):
        """Update the label when theme changes."""
        self._render_latex()
