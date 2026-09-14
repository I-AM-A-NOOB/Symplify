# coding: utf-8
"""History model for the QML Symplify app.

A QAbstractListModel of calculation entries rendered as cards by the
history page. Each entry stores its input (name/operator/expression for
assignments), and then either the sympy-format result with the result's
LaTeX source, or — when the request failed — the failure text. Failed
entries are kept on purpose: they carry the input back, so a typo can be
sent to the input area and fixed. The rendered SVG data URL is produced
lazily per visible row and re-tinted when the theme color changes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Slot
from PySide6.QtGui import QColor

from ..latex_render import latex_to_svg, svg_size


@dataclass
class HistoryItem:
    """One calculation entry, stored ready for display.

    Attributes:
        expression: The evaluated expression (value part for assignments).
        result: The sympy-format result string ("" for a failed entry).
        error: Failure text (message plus hint) for a failed entry, "" otherwise.
            A non-empty value is what makes the card render as an error card.
        mode: "Code" or "Assign".
        name: Assignment target variable ("" for code entries).
        op: Assignment operator ("=", "+=", ...; "=" for code entries).
        latex: LaTeX source of the result (for rendering and copying).
        svg_url: Cached rendered SVG data URL; rendered lazily.
        created: Wall-clock time of the entry. Must be a ``default_factory``:
            a plain ``= datetime.now()`` default is evaluated once at class
            definition, which stamped every entry with the import time.
    """

    expression: str
    result: str
    error: str = ""
    mode: str = "Code"
    name: str = ""
    op: str = "="
    latex: str = ""
    svg_url: Optional[str] = None
    natural_w: int = 0
    natural_h: int = 0
    created: datetime = field(default_factory=datetime.now)


class HistoryModel(QAbstractListModel):
    """List model of calculation history entries.

    Roles: mode / name / op / expression / result / error / latexUrl / latex /
    time. The ``latexUrl`` role renders (and caches) the entry's result SVG with
    the current theme color on first access; ``error`` is non-empty exactly for
    the entries whose request failed.
    """

    ModeRole = Qt.UserRole + 1
    NameRole = Qt.UserRole + 2
    OpRole = Qt.UserRole + 3
    ExpressionRole = Qt.UserRole + 4
    ResultRole = Qt.UserRole + 5
    LatexUrlRole = Qt.UserRole + 6
    LatexRole = Qt.UserRole + 7
    NaturalWidthRole = Qt.UserRole + 8
    NaturalHeightRole = Qt.UserRole + 9
    TimeRole = Qt.UserRole + 10
    ErrorRole = Qt.UserRole + 11

    def __init__(self, parent=None):
        """Initialize the history model."""
        super().__init__(parent)
        self._items: List[HistoryItem] = []
        self._latex_color: str = "#000000"
        self._latex_size: int = 24
        self._latex_font: str = ""

    def roleNames(self):
        return {
            self.ModeRole: b"mode",
            self.NameRole: b"name",
            self.OpRole: b"op",
            self.ExpressionRole: b"expression",
            self.ResultRole: b"result",
            self.ErrorRole: b"error",
            self.LatexUrlRole: b"latexUrl",
            self.LatexRole: b"latex",
            self.NaturalWidthRole: b"naturalWidth",
            self.NaturalHeightRole: b"naturalHeight",
            self.TimeRole: b"time",
        }

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of history entries."""
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.ModeRole:
            return item.mode
        if role == self.NameRole:
            return item.name
        if role == self.OpRole:
            return item.op
        if role == self.ExpressionRole:
            return item.expression
        if role == self.ResultRole:
            return item.result
        if role == self.ErrorRole:
            return item.error
        if role == self.LatexUrlRole:
            return self._svg_url(index.row())
        if role == self.LatexRole:
            return item.latex
        if role == self.NaturalWidthRole:
            return item.natural_w
        if role == self.NaturalHeightRole:
            return item.natural_h
        if role == self.TimeRole:
            return item.created.strftime("%H:%M:%S")
        if role == Qt.DisplayRole:
            return item.expression
        return None

    def _svg_url(self, row: int) -> str:
        """Render (once) and return the entry's SVG data URL."""
        item = self._items[row]
        if item.svg_url is None:
            svg = latex_to_svg(
                item.latex,
                size=self._latex_size,
                color=self._latex_color,
                font=self._latex_font,
            )
            item.svg_url = (
                "data:image/svg+xml;charset=utf-8," + quote(svg, safe="")
                if svg else ""
            )
            item.natural_w, item.natural_h = svg_size(svg)
            # Re-notify so the visible delegate re-reads the final sizes.
            self.dataChanged.emit(
                self.index(row, 0), self.index(row, 0),
                [self.LatexUrlRole, self.NaturalWidthRole, self.NaturalHeightRole],
            )
        return item.svg_url

    @Slot(str)
    def set_latex_color(self, color: str) -> None:
        """Re-tint all rendered entries (called on theme changes)."""
        qcolor = QColor(color)
        if not qcolor.isValid() or qcolor.name() == self._latex_color:
            return
        self._latex_color = qcolor.name()
        if self._items:
            for item in self._items:
                item.svg_url = None
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._items) - 1, 0),
                [self.LatexUrlRole, self.NaturalWidthRole, self.NaturalHeightRole],
            )

    @Slot(int)
    def set_latex_size(self, size: int) -> None:
        """Re-render every entry at a new font size (settings page).

        Mirrors :meth:`set_latex_color`: cached SVGs are dropped so each entry is
        rendered again on demand with the new size.
        """
        size = int(size)
        if size == self._latex_size:
            return
        self._latex_size = size
        if self._items:
            for item in self._items:
                item.svg_url = None
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._items) - 1, 0),
                [self.LatexUrlRole, self.NaturalWidthRole, self.NaturalHeightRole],
            )

    @Slot(str)
    def set_latex_font(self, font: str) -> None:
        """Re-render every entry with a different LaTeX font.

        Mirrors :meth:`set_latex_size`: cached SVGs are dropped so each entry is
        rendered again on demand. ``font`` is a font file path ('' = bundled).
        """
        font = font or ""
        if font == self._latex_font:
            return
        self._latex_font = font
        if self._items:
            for item in self._items:
                item.svg_url = None
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._items) - 1, 0),
                [self.LatexUrlRole, self.NaturalWidthRole, self.NaturalHeightRole],
            )

    def add_item(self, expression: str, result: str, mode: str = "Code",
                 latex: str = "", name: str = "", op: str = "=",
                 error: str = "") -> None:
        """Insert a history entry at the TOP of the list.

        ``error`` marks a failed request: the card then shows the failure text
        instead of a result, and the input is still there to be sent back.
        """
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._items.insert(
            0,
            HistoryItem(
                expression=expression,
                result=result,
                error=error,
                mode=mode,
                name=name,
                op=op,
                latex=latex,
            ),
        )
        self.endInsertRows()

    @Slot()
    def clear(self) -> None:
        """Clear all history entries (granular removal, no reset flash)."""
        if not self._items:
            return
        self.beginRemoveRows(QModelIndex(), 0, len(self._items) - 1)
        self._items.clear()
        self.endRemoveRows()

    @Slot(result=int)
    def count(self) -> int:
        """Number of entries, callable from QML."""
        return len(self._items)
