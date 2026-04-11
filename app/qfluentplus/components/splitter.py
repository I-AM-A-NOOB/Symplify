# coding: utf-8
"""Fluent style splitter components.

This module provides a custom splitter with a fluent design style handle,
featuring a capsule-shaped indicator that highlights on hover.

Example:
    >>> from PySide6.QtCore import Qt
    >>> from app.qfluentplus.components.splitter import Splitter
    >>>
    >>> splitter = Splitter(Qt.Orientation.Horizontal)
    >>> splitter.addWidget(left_panel)
    >>> splitter.addWidget(right_panel)
"""
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QSplitter, QSplitterHandle

from qfluentwidgets import isDarkTheme

from ..common.style_sheet import StyleSheet


class SplitterHandle(QSplitterHandle):
    """Fluent style splitter handle with capsule indicator.

    A custom splitter handle that displays a capsule-shaped indicator
    in the center. The handle highlights with a semi-transparent
    background on hover.

    Attributes:
        isHover (bool): Whether the mouse is currently hovering over the handle.

    Example:
        >>> handle = SplitterHandle(Qt.Orientation.Horizontal, parent_splitter)
    """

    def __init__(self, orientation: Qt.Orientation, parent: QSplitter = None):
        """Initialize the splitter handle.

        Args:
            orientation: The orientation of the handle (Horizontal or Vertical).
            parent: The parent QSplitter widget.
        """
        super().__init__(orientation, parent)
        self.isHover = False

    def sizeHint(self) -> QSize:
        """Return the recommended size for the handle.

        Returns:
            A QSize with width 15 for horizontal or height 15 for vertical.
        """
        if self.orientation() == Qt.Orientation.Horizontal:
            return QSize(15, super().sizeHint().height())
        return QSize(super().sizeHint().width(), 15)

    def enterEvent(self, event):
        """Handle mouse enter event.

        Sets isHover to True and triggers a repaint.

        Args:
            event: The enter event (unused).
        """
        self.isHover = True
        self.update()

    def leaveEvent(self, event):
        """Handle mouse leave event.

        Sets isHover to False and triggers a repaint.

        Args:
            event: The leave event (unused).
        """
        self.isHover = False
        self.update()

    def _hoverBackgroundColor(self) -> QColor:
        """Get the hover background color.

        Returns:
            QColor for hover background with theme-aware alpha.
        """
        return QColor(191, 191, 191, 63)

    def _capsuleColor(self) -> QColor:
        """Get the capsule indicator color.

        Returns:
            Theme-aware QColor for the capsule indicator.
        """
        if isDarkTheme():
            return QColor(200, 200, 200, 180)
        return QColor(127, 127, 127, 200)

    def paintEvent(self, event):
        """Paint the handle with capsule indicator.

        Draws a hover background if the mouse is over the handle,
        followed by a capsule-shaped indicator in the center.

        Args:
            event: The paint event.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Draw hover background
        if self.isHover:
            painter.setBrush(QBrush(self._hoverBackgroundColor()))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(self.rect())

        # Draw capsule indicator with theme-aware color
        painter.setBrush(QBrush(self._capsuleColor()))
        painter.setPen(Qt.PenStyle.NoPen)

        capsule_width = 4
        capsule_length = 30
        radius = 2

        if self.orientation() == Qt.Orientation.Horizontal:
            x = (self.width() - capsule_width) // 2
            y = (self.height() - capsule_length) // 2
            painter.drawRoundedRect(
                QRect(x, y, capsule_width, capsule_length), radius, radius
            )
        else:
            x = (self.width() - capsule_length) // 2
            y = (self.height() - capsule_width) // 2
            painter.drawRoundedRect(
                QRect(x, y, capsule_length, capsule_width), radius, radius
            )


class Splitter(QSplitter):
    """Fluent style splitter with custom handle.

    A QSplitter subclass that uses SplitterHandle for its handles,
    providing a fluent design style with capsule indicators.

    The splitter has a handle width of 20 pixels and children are
    not collapsible by default. The style sheet is automatically
    applied on initialization.

    Example:
        >>> from PySide6.QtWidgets import QWidget, QVBoxLayout
        >>>
        >>> splitter = Splitter(Qt.Orientation.Horizontal)
        >>> left = QWidget()
        >>> right = QWidget()
        >>> splitter.addWidget(left)
        >>> splitter.addWidget(right)
    """

    def __init__(
        self, orientation: Qt.Orientation = Qt.Orientation.Horizontal, parent=None
    ):
        """Initialize the splitter.

        Automatically applies the SPLITTER style sheet.

        Args:
            orientation: The orientation of the splitter. Defaults to Horizontal.
            parent: The parent widget. Defaults to None.
        """
        super().__init__(orientation, parent)
        self._handleWidth = 20
        self.setHandleWidth(self._handleWidth)
        self.setChildrenCollapsible(False)

        # Apply style sheet automatically
        StyleSheet.SPLITTER.apply(self)

    def getHandleWidth(self) -> int:
        """Get the width of the splitter handle.

        Returns:
            The handle width in pixels.
        """
        return self._handleWidth

    def setHandleWidth(self, width: int):
        """Set the width of the splitter handle.

        Args:
            width: The handle width in pixels. Minimum value is 6.
        """
        self._handleWidth = max(6, width)
        super().setHandleWidth(self._handleWidth)

    def createHandle(self) -> QSplitterHandle:
        """Create a custom splitter handle.

        Returns:
            A new SplitterHandle instance.
        """
        return SplitterHandle(self.orientation(), self)
