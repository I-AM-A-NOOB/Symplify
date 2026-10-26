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

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, Qt, Signal, Slot

from ..latex_render import LatexStyle
from .latex_service import LatexRenderService


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
        requested: True while this item's render is queued or running.
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
    svg_url: str | None = None
    natural_w: int = 0
    natural_h: int = 0
    requested: bool = False
    created: datetime = field(default_factory=datetime.now)


class HistoryModel(QAbstractListModel):
    """List model of calculation history entries.

    Roles: mode / name / op / expression / result / error / latexUrl / latex /
    time. ``latexUrl`` is a cache lookup; the view queues the artwork through
    ``requestLatex`` and receives it later via ``dataChanged``. ``error`` is
    non-empty exactly for the entries whose request failed.
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

    countChanged = Signal()

    def __init__(self, parent=None, latex_service=None):
        """Initialize the history model.

        Args:
            latex_service: Shared renderer. None creates one; with no
                QCoreApplication it renders inline, which keeps the model tests
                synchronous.
        """
        super().__init__(parent)
        self._items: list[HistoryItem] = []
        #: Theme ink, font size and LaTeX font file, in one value.
        self._latex_style = LatexStyle()
        self._latex_service = latex_service or LatexRenderService(self)
        #: token -> item; row indexes move when entries are inserted at the top.
        self._latex_pending: dict[str, HistoryItem] = {}
        self._latex_seq = 0
        self._latex_service.rendered.connect(self._on_latex_rendered)
        self._latex_service.failed.connect(self._on_latex_failed)

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
            # Not `self._svg_url(...)`: rendering here would make every read — and
            # so every delegate that is built — render its entry. The view asks for
            # the render via `requestLatex` when the card comes near the viewport,
            # and `dataChanged` brings the result back to the binding.
            return item.svg_url or ""
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

    @Slot(int)
    def requestLatex(self, row: int) -> None:
        """Queue the entry's SVG if it has not been rendered yet.

        Called by the view when a card comes near the viewport. Reading the
        ``latexUrl`` role stays a cache lookup; this is the only thing that
        queues work, and the completion arrives through ``dataChanged``.
        """
        if not 0 <= row < len(self._items):
            return
        item = self._items[row]
        if item.svg_url is not None or item.requested:
            return
        item.requested = True
        self._latex_seq += 1
        token = f"history:{self._latex_seq}"
        self._latex_pending[token] = item
        self._latex_service.request(
            token, item.latex, self._latex_style, owner="history"
        )

    def _row_of(self, item: HistoryItem) -> int | None:
        """Current row for an item; entries can shift after a new calculation."""
        for row, candidate in enumerate(self._items):
            if candidate is item:
                return row
        return None

    def _on_latex_rendered(
        self, token: str, url: str, width: int, height: int
    ) -> None:
        item = self._latex_pending.pop(token, None)
        if item is None:
            return
        item.svg_url = url
        item.natural_w = width
        item.natural_h = height
        item.requested = False
        row = self._row_of(item)
        if row is not None:
            self.dataChanged.emit(
                self.index(row, 0), self.index(row, 0),
                [self.LatexUrlRole, self.NaturalWidthRole, self.NaturalHeightRole],
            )

    def _on_latex_failed(self, token: str, message: str) -> None:
        item = self._latex_pending.pop(token, None)
        if item is not None:
            item.requested = False

    def set_latex_style(self, style: LatexStyle) -> None:
        """Drop cached SVGs and re-render lazily in a new style.

        Queued renders from the old style are invalidated by the service's
        history generation; the cards request again when they are next near the
        viewport.
        """
        if style == self._latex_style:
            return
        self._latex_style = style
        self._latex_service.begin_generation("history")
        self._latex_pending.clear()
        if self._items:
            for item in self._items:
                item.svg_url = None
                item.requested = False
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
        self.countChanged.emit()

    @Slot()
    def clear(self) -> None:
        """Clear all history entries (granular removal, no reset flash)."""
        if not self._items:
            return
        self._latex_service.begin_generation("history")
        self._latex_pending.clear()
        self.beginRemoveRows(QModelIndex(), 0, len(self._items) - 1)
        self._items.clear()
        self.endRemoveRows()
        self.countChanged.emit()

    def _get_count(self) -> int:
        """Number of entries."""
        return len(self._items)

    count = Property(int, _get_count, notify=countChanged)
