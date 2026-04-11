# coding: utf-8
"""QFluentPlus style sheet management.

This module provides theme-aware style sheet support for QFluentPlus components,
following the same pattern as Gallery's style sheet management.

Example:
    >>> from app.qfluentplus.common.style_sheet import StyleSheet
    >>> StyleSheet.SPLITTER.apply(widget)
"""
from enum import Enum

from qfluentwidgets import StyleSheetBase, Theme, qconfig


class StyleSheet(StyleSheetBase, Enum):
    """QFluentPlus component style sheets.

    Each enum value corresponds to a QSS file in the resource system.
    The QSS files should be located at:
        :/qfluentplus/qss/light/{name}.qss
        :/qfluentplus/qss/dark/{name}.qss

    Attributes:
        SPLITTER: Style sheet for Splitter component.
        PLOT_WIDGET: Style sheet for MathPlotWidget component.
        PLOT_TOOLBAR: Style sheet for MathPlotToolbar component.
        LATEX_LABEL: Style sheet for LaTeXLabel component.
    """

    SPLITTER = "splitter"
    PLOT_WIDGET = "plot_widget"
    PLOT_TOOLBAR = "plot_toolbar"
    LATEX_LABEL = "latex_label"

    def path(self, theme: Theme = Theme.AUTO) -> str:
        """Get the style sheet file path for the specified theme.

        Args:
            theme: The theme to get the style sheet for. Defaults to Theme.AUTO,
                which uses the current application theme from qconfig.

        Returns:
            The resource path to the QSS file.
        """
        theme = qconfig.theme if theme == Theme.AUTO else theme
        return f":/qfluentplus/qss/{theme.value.lower()}/{self.value}.qss"
