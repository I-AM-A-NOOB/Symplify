# coding: utf-8
"""History interface for the Symplify application.

This module provides a simple history display interface for viewing
calculation history.

Example:
    >>> from app.view.history_interface import HistoryInterface
    >>> history_interface = HistoryInterface()
    >>> history_interface.set_history_items(history_items)
"""
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QAbstractItemView,
    QHeaderView,
)

from qfluentwidgets import (
    ScrollArea,
    TableWidget,
    PushButton,
    SubtitleLabel,
    FluentIcon,
    ToolTipFilter,
    ToolTipPosition,
)

from ..viewmodel import HistoryItem


class HistoryInterface(ScrollArea):
    """History display interface.

    A simple view-only interface for displaying calculation history.

    Attributes:
        table: The table widget displaying history.

    Example:
        >>> interface = HistoryInterface()
        >>> interface.set_history_items(history_items)
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the history interface.

        Args:
            parent: The parent widget. Defaults to None.
        """
        super().__init__(parent)

        self._setup_ui()
        self._setup_style()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create container widget
        self.container = QWidget(self)
        self.setWidget(self.container)
        self.setWidgetResizable(True)

        # Main layout
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title
        title_label = SubtitleLabel(self.tr("Calculation History"), self)
        layout.addWidget(title_label)

        # History table
        self.table = TableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            [
                self.tr("Expression"),
                self.tr("Result"),
                self.tr("Mode"),
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Clear button
        self.clear_button = PushButton(self.tr("Clear History"), self)
        self.clear_button.setIcon(FluentIcon.DELETE)
        self.clear_button.setToolTip(self.tr("Clear all history"))
        self.clear_button.installEventFilter(
            ToolTipFilter(self.clear_button, 300, ToolTipPosition.TOP)
        )
        button_layout.addWidget(self.clear_button)

        layout.addLayout(button_layout)

    def _setup_style(self) -> None:
        """Apply styling to the interface."""
        # Enable transparent background
        self.setStyleSheet("background: transparent; border: none;")
        self.container.setStyleSheet("background: transparent;")

    def set_history_items(self, items: List[HistoryItem]) -> None:
        """Set the history items to display.

        Args:
            items: List of history items.
        """
        self.table.setRowCount(len(items))

        for i, item in enumerate(items):
            # Expression column
            expr_item = self.table.item(i, 0)
            if not expr_item:
                expr_item = self._create_table_item(item.expression)
                self.table.setItem(i, 0, expr_item)
            else:
                expr_item.setText(item.expression)

            # Result column
            result_text = (
                str(item.result.value)
                if item.result.success
                else f"Error: {item.result.error}"
            )
            result_item = self.table.item(i, 1)
            if not result_item:
                result_item = self._create_table_item(result_text)
                self.table.setItem(i, 1, result_item)
            else:
                result_item.setText(result_text)

            # Mode column
            mode_text = "Code" if item.mode.name == "CODE" else "Assign"
            mode_item = self.table.item(i, 2)
            if not mode_item:
                mode_item = self._create_table_item(mode_text)
                self.table.setItem(i, 2, mode_item)
            else:
                mode_item.setText(mode_text)

    def _create_table_item(self, text: str):
        """Create a table widget item.

        Args:
            text: The item text.

        Returns:
            The table widget item.
        """
        from PySide6.QtWidgets import QTableWidgetItem

        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def clear_history(self) -> None:
        """Clear the history display."""
        self.table.setRowCount(0)
