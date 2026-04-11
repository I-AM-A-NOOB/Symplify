# coding: utf-8
"""History ViewModel for the Symplify application.

This module provides the ViewModel for managing calculation history,
storing and retrieving past calculations.

Example:
    >>> from app.viewmodel import HistoryViewModel
    >>> vm = HistoryViewModel()
    >>> vm.add_item("2 + 2", result, InputMode.CODE)
"""

from typing import Optional, List
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from ..model.calculator import CalculationResult
from ..common.input_mode import InputMode


@dataclass
class HistoryItem:
    """A single history item.

    Attributes:
        expression: The input expression.
        result: The calculation result.
        mode: The input mode used.
    """

    expression: str
    result: CalculationResult
    mode: InputMode


class HistoryViewModel(QObject):
    """ViewModel for calculation history.

    Manages a list of past calculations, providing add, clear,
    and retrieve operations.

    Signals:
        history_updated: Emitted when history changes.
        item_added: Emitted when a new item is added.
            Args:
                item: The added history item.

    Attributes:
        _history: Internal list of history items.

    Example:
        >>> vm = HistoryViewModel()
        >>> vm.history_updated.connect(view.refresh)
        >>> vm.add_item("2 + 2", result, InputMode.CODE)
    """

    history_updated = Signal()
    item_added = Signal(HistoryItem)

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize the history ViewModel.

        Args:
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._history: List[HistoryItem] = []

    def add_item(
        self, expression: str, result: CalculationResult, mode: InputMode
    ) -> None:
        """Add an item to history.

        Args:
            expression: The input expression.
            result: The calculation result.
            mode: The input mode used.
        """
        item = HistoryItem(expression, result, mode)
        self._history.append(item)
        self.item_added.emit(item)
        self.history_updated.emit()

    def get_history(self) -> List[HistoryItem]:
        """Get all history items.

        Returns:
            List of history items (newest first).
        """
        return self._history.copy()

    def get_recent(self, count: int = 10) -> List[HistoryItem]:
        """Get recent history items.

        Args:
            count: Number of items to return. Defaults to 10.

        Returns:
            List of recent history items.
        """
        return self._history[-count:].copy()

    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()
        self.history_updated.emit()

    def get_item_count(self) -> int:
        """Get the number of history items.

        Returns:
            The count of history items.
        """
        return len(self._history)
