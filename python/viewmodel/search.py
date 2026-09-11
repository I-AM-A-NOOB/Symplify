# coding: utf-8
"""Live search filters for the Variables and History pages.

Both pages have a search box whose match mode can be switched. Filtering lives in
a ``QSortFilterProxyModel`` over the shared source model rather than inside the
models themselves: the models stay single-purpose (the calculator writes into
``VariablesModel``, and ``HistoryModel`` is the history of record), while Qt owns
the hard part — keeping the visible rows and their insert/remove signals correct
while a filter is active.

Consequence for the pages: whatever row indices they build must come from the
**proxy**, not the source model (see VariablesPage's selection model and edit
path). ``fuzzy`` means "contains the query in any of the mode's fields"; an empty
query matches everything, so clearing the box restores the full list.
"""

from enum import Enum

from PySide6.QtCore import (
    Property,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
    Slot,
)

from .history_viewmodel import HistoryModel


class VariableSearchMode(Enum):
    """Variables page match modes, in the order the UI lists them."""

    FUZZY = 0  # name + value + type
    NAME = 1
    VALUE = 2
    TYPE = 3


class HistorySearchMode(Enum):
    """History page match modes, in the order the UI lists them.

    ``EXPRESSION`` matches the input as the card shows it: for an assignment that
    is the whole ``name op expression`` statement, not just the right-hand side,
    which is why there is no separate name mode. ``RESULT`` matches the computed
    result *or* the failure text, which is why there is no separate error mode.
    """

    FUZZY = 0  # the input line + result + failure text
    EXPRESSION = 1
    RESULT = 2


def matches(haystack, needle: str) -> bool:
    """Case-insensitive containment; an empty ``needle`` matches anything.

    ``haystack`` may be None (a role that does not apply to an entry).
    """
    if not needle:
        return True
    return needle.casefold() in str(haystack or "").casefold()


class SearchFilterModel(QSortFilterProxyModel):
    """Search state and matching plumbing shared by both page filters.

    Subclasses implement ``fields`` — which strings a given mode searches.
    """

    searchChanged = Signal()

    def __init__(self, parent=None):
        """Initialize the filter with an empty query in mode 0 (fuzzy)."""
        super().__init__(parent)
        self._text = ""
        self._mode = 0
        # Re-filter when the source model changes, so an entry that stops (or
        # starts) matching an active query appears/disappears on its own.
        self.setDynamicSortFilter(True)

    def fields(self, source_row: int) -> list:
        """The strings the current mode searches for one source row."""
        raise NotImplementedError

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Accept a row when any of its searchable fields contains the query."""
        if not self._text:
            return True
        return any(matches(field, self._text) for field in self.fields(source_row))

    def _get_search_text(self) -> str:
        return self._text

    def _set_search_text(self, text: str) -> None:
        text = text or ""
        if text != self._text:
            self._text = text
            self.invalidateRowsFilter()
            self.searchChanged.emit()

    def _get_search_mode(self) -> int:
        return self._mode

    def _set_search_mode(self, mode: int) -> None:
        mode = int(mode)
        if mode != self._mode:
            self._mode = mode
            self.invalidateRowsFilter()
            self.searchChanged.emit()

    searchText = Property(
        str, _get_search_text, _set_search_text, notify=searchChanged
    )
    searchMode = Property(
        int, _get_search_mode, _set_search_mode, notify=searchChanged
    )

    @Slot()
    def clearSearch(self) -> None:
        """Empty the query, which restores every row."""
        self._set_search_text("")


class VariablesFilterModel(SearchFilterModel):
    """Visible variables for the Variables page search box.

    Columns are name / value / type, so the modes map straight onto them.
    """

    def fields(self, source_row: int) -> list:
        """The column(s) the current mode searches."""
        model = self.sourceModel()
        columns = [model.data(model.index(source_row, c), Qt.DisplayRole)
                   for c in range(3)]
        mode = VariableSearchMode(self._mode)
        if mode is VariableSearchMode.NAME:
            return columns[0:1]
        if mode is VariableSearchMode.VALUE:
            return columns[1:2]
        if mode is VariableSearchMode.TYPE:
            return columns[2:3]
        return columns

    @Slot(int, int, result=QModelIndex)
    def modelIndex(self, row: int, column: int) -> QModelIndex:
        """Build a proxy index for QML (the table's edit path needs this one)."""
        return self.index(row, column)

    @Slot(int, int, result=str)
    def cellAt(self, row: int, column: int) -> str:
        """Return the visible cell text at (row, column)."""
        if 0 <= row < self.rowCount() and 0 <= column < 3:
            return str(self.data(self.index(row, column), Qt.DisplayRole) or "")
        return ""

    @Slot(int, result=str)
    def nameAt(self, row: int) -> str:
        """Return the visible variable name at ``row`` (or an empty string)."""
        return self.cellAt(row, 0)


class HistoryFilterModel(SearchFilterModel):
    """Visible history cards for the History page search box."""

    def fields(self, source_row: int) -> list:
        """The input line (plus result and failure text) the mode searches."""
        model = self.sourceModel()
        index = model.index(source_row, 0)
        expression = model.data(index, HistoryModel.ExpressionRole)
        result = model.data(index, HistoryModel.ResultRole)
        error = model.data(index, HistoryModel.ErrorRole)

        # The input line as the card renders it. An assignment reads as a whole
        # statement, so its name and operator are searchable through it.
        statement = expression
        if model.data(index, HistoryModel.ModeRole) == "Assign":
            name = model.data(index, HistoryModel.NameRole) or ""
            op = model.data(index, HistoryModel.OpRole) or "="
            statement = f"{name} {op} {expression}".strip()

        mode = HistorySearchMode(self._mode)
        if mode is HistorySearchMode.EXPRESSION:
            return [statement]
        if mode is HistorySearchMode.RESULT:
            return [result, error]
        return [statement, result, error]
