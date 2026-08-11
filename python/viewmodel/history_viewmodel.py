# coding: utf-8
"""History model for the QML Symplify app.

A QAbstractTableModel so Qt Quick Controls' TableView renders the
history as a real multi-column table (expression / result / mode).
"""

from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


@dataclass
class HistoryItem:
    """A single history entry, stored ready for display."""

    expression: str
    result: str
    mode: str


class HistoryModel(QAbstractTableModel):
    """Table model of calculation history.

    Roles:
        expression: The input expression.
        result: The formatted result text.
        mode: The input mode ("Code" or "Assign").
    """

    ExpressionRole = Qt.UserRole + 1
    ResultRole = Qt.UserRole + 2
    ModeRole = Qt.UserRole + 3

    def __init__(self, parent=None):
        """Initialize the history model."""
        super().__init__(parent)
        self._items: List[HistoryItem] = []

    def roleNames(self):
        return {
            self.ExpressionRole: b"expression",
            self.ResultRole: b"result",
            self.ModeRole: b"mode",
        }

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of history rows."""
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the fixed column count (expression, result, mode)."""
        return 0 if parent.isValid() else 3

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.ExpressionRole:
            return item.expression
        if role == self.ResultRole:
            return item.result
        if role == self.ModeRole:
            return item.mode
        if role == Qt.DisplayRole:
            return [item.expression, item.result, item.mode][index.column()]
        return None

    def add_item(self, expression: str, result: str, mode: str) -> None:
        """Append a history entry and notify views."""
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(HistoryItem(expression, result, mode))
        self.endInsertRows()

    def clear(self) -> None:
        """Clear all history entries."""
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()
