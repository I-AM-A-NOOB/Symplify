"""History model for the QML Symplify app.

A QAbstractListModel of calculation entries rendered as cards by the
history page. Each entry stores its input (name/operator/expression for
assignments), and then either the sympy-format result with the result's
LaTeX source, or — when the request failed — the failure text. Failed
entries are kept on purpose: they carry the input back, so a typo can be
sent to the input area and fixed. The rendered SVG data URL is produced
lazily per visible row and re-tinted when the theme color changes.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QAbstractProxyModel,
    QModelIndex,
    Qt,
    Signal,
    Slot,
)

from ..latex_render import LatexStyle
from .latex_jobs import LatexJobs
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
        canonical_input: Syntax-normalized input text, kept for the
            Send-normalized action; empty when it could not be generated.
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
    canonical_input: str = ""
    svg_url: str | None = None
    natural_w: int = 0
    natural_h: int = 0
    requested: bool = False
    created: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """The durable half of an entry, for ``history.json``.

        The rendered SVG and its natural size are deliberately absent: they are
        a cache for the current style and are regenerated lazily after a reload.
        """
        return {
            "expression": self.expression,
            "result": self.result,
            "error": self.error,
            "mode": self.mode,
            "name": self.name,
            "op": self.op,
            "latex": self.latex,
            "canonical_input": self.canonical_input,
            "created": self.created.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "HistoryItem":
        """Build an entry from persisted JSON, rejecting a non-object.

        Unknown fields are ignored so a newer/older writer can still be read;
        missing strings default to the same empty values as a new entry. A bad
        timestamp starts a new one rather than dropping the whole entry.
        """
        if not isinstance(data, dict):
            raise ValueError("history entry is not an object")

        def text(name: str) -> str:
            value = data.get(name, "")
            return value if isinstance(value, str) else ""

        mode = text("mode")
        if mode not in ("Code", "Assign"):
            mode = "Code"
        created = datetime.now()
        raw_created = data.get("created")
        if isinstance(raw_created, str):
            try:
                created = datetime.fromisoformat(raw_created)
            except ValueError:
                pass
        return cls(
            expression=text("expression"),
            result=text("result"),
            error=text("error"),
            mode=mode,
            name=text("name"),
            op=text("op") or "=",
            latex=text("latex"),
            canonical_input=text("canonical_input"),
            created=created,
        )


class HistoryModel(QAbstractListModel):
    """List model of calculation history entries.

    Roles: mode / name / op / expression / result / error / canonicalInput /
    latexUrl / latex / time. ``latexUrl`` is a cache lookup; the view queues the
    artwork through ``requestLatex`` and receives it later via ``dataChanged``.
    ``error`` is non-empty exactly for the entries whose request failed.

    The list is bounded: an entry past ``MAX_HISTORY_ENTRIES`` evicts the oldest
    one, releasing its rendered SVG with it. When a ``path`` is supplied, the
    durable fields are written atomically to ``history.json`` after every add or
    clear and loaded at startup; the SVG data URLs are cache, not persisted.
    The bound is what keeps rendered artwork from growing without limit.
    """

    #: Oldest entries are dropped past this many. Large enough for a real
    #: session, small enough that rendered SVG data URLs cannot grow forever.
    MAX_HISTORY_ENTRIES = 500

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
    CanonicalInputRole = Qt.UserRole + 12

    countChanged = Signal()

    def __init__(self, parent=None, latex_service=None, path: Path | str | None = None):
        """Initialize the history model.

        Args:
            latex_service: Shared renderer. None creates one; with no
                QCoreApplication it renders inline, which keeps the model tests
                synchronous.
            path: Optional ``history.json``. The application passes the file
                beside ``config.yaml``; tests/headless callers leave it None.
        """
        super().__init__(parent)
        self._path = Path(path) if path is not None else None
        self.load_error = ""
        self.save_error = ""
        self._items: list[HistoryItem] = []
        #: Theme ink, font size and LaTeX font file, in one value.
        self._latex_style = LatexStyle()
        self._latex_service = latex_service or LatexRenderService(self)
        #: The artwork requests; the target is the item itself, because row
        #: indexes move when entries are inserted at the top.
        self._latex_jobs = LatexJobs(self._latex_service, "history", self)
        self._latex_jobs.rendered.connect(self._on_latex_rendered)
        self._latex_jobs.failed.connect(self._on_latex_failed)
        self._load()

    def roleNames(self):
        return {
            self.ModeRole: b"mode",
            self.NameRole: b"name",
            self.OpRole: b"op",
            self.ExpressionRole: b"expression",
            self.ResultRole: b"result",
            self.ErrorRole: b"error",
            self.CanonicalInputRole: b"canonicalInput",
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
        if role == self.CanonicalInputRole:
            return item.canonical_input
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
        self._latex_jobs.request(item, item.latex, self._latex_style)

    def _row_of(self, item: HistoryItem) -> int | None:
        """Current row for an item; entries can shift after a new calculation."""
        for row, candidate in enumerate(self._items):
            if candidate is item:
                return row
        return None

    def _on_latex_rendered(
        self, item: HistoryItem, url: str, width: int, height: int
    ) -> None:
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

    def _on_latex_failed(self, item: HistoryItem, message: str) -> None:
        item.requested = False

    def set_latex_style(self, style: LatexStyle, invalidate: bool = True) -> None:
        """Take a new style, and re-render now unless a burst is in progress.

        A single change invalidates every cached SVG at once; later steps of a
        size drag only move the style, and `refresh_latex_artwork` runs once when
        the burst ends.
        """
        if style == self._latex_style:
            return
        self._latex_style = style
        if invalidate:
            self.refresh_latex_artwork()

    def refresh_latex_artwork(self) -> None:
        """Drop cached SVGs and re-render lazily in the current style.

        Queued renders from the old style are invalidated by the service's
        history generation; the cards request again when they are next near the
        viewport.
        """
        self._latex_jobs.reset()
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
                 error: str = "", canonical_input: str = "") -> None:
        """Insert a history entry at the TOP of the list.

        ``error`` marks a failed request: the card then shows the failure text
        instead of a result, and the input is still there to be sent back.
        Beyond ``MAX_HISTORY_ENTRIES`` the oldest entry is evicted first; its
        ``HistoryItem`` (and cached SVG data URL) is dropped with it.
        """
        if len(self._items) >= self.MAX_HISTORY_ENTRIES:
            last = len(self._items) - 1
            self.beginRemoveRows(QModelIndex(), last, last)
            self._items.pop()
            self.endRemoveRows()
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
                canonical_input=canonical_input,
            ),
        )
        self.endInsertRows()
        self.countChanged.emit()
        self._save()

    @Slot()
    def clear(self) -> None:
        """Clear all history entries (granular removal, no reset flash)."""
        if not self._items:
            return
        self._latex_jobs.reset()
        self.beginRemoveRows(QModelIndex(), 0, len(self._items) - 1)
        self._items.clear()
        self.endRemoveRows()
        self.countChanged.emit()
        self._save()

    # --- persistence ------------------------------------------------------
    def _load(self) -> None:
        """Load ``history.json`` if a path was supplied.

        A corrupt file is moved aside (``.corrupt``) rather than overwritten, so
        the app starts with an empty history but the failed data remains for
        inspection. Loading never touches the renderer cache.
        """
        path = self._path
        if path is None or not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            entries = raw.get("entries") if isinstance(raw, dict) else raw
            if not isinstance(entries, list):
                raise ValueError("history file has no entries list")
            loaded = [
                HistoryItem.from_dict(entry)
                for entry in entries[: self.MAX_HISTORY_ENTRIES]
            ]
        except (OSError, ValueError, TypeError) as exc:
            self.load_error = f"history not loaded: {exc}"
            try:
                os.replace(path, path.with_suffix(path.suffix + ".corrupt"))
            except OSError:
                pass
            return
        self._items = loaded

    def _save(self) -> None:
        """Write the durable entries atomically, ignoring a write failure."""
        path = self._path
        if path is None:
            return
        payload = {
            "version": 1,
            "entries": [item.to_dict() for item in self._items],
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(temporary, path)
            self.save_error = ""
        except OSError as exc:
            self.save_error = f"history not written: {exc}"

    def _get_count(self) -> int:
        """Number of entries."""
        return len(self._items)

    count = Property(int, _get_count, notify=countChanged)


class HistoryWindowModel(QAbstractProxyModel):
    """The first ``limit`` rows of the history view.

    The History page builds one card per row. Without a window it built every
    card the moment the page opened — hundreds of object trees and two
    rich-text bindings each — while only ``loaded`` of them were revealed. The
    page wraps its search proxy in this one and raises ``limit`` a batch at a
    time, so the cards beyond the revealed batch never exist.

    Rows map 1:1 onto the source proxy (the search filter), so a window row index
    is still the proxy row index the page's search and reveal arithmetic use. A
    plain ``QSortFilterProxyModel`` cannot do this job: with a row count that is
    a property of the source's *length*, changing ``limit`` made it emit only
    ``layoutChanged``, and the Repeater built no cards at all (measured). This
    proxy emits the structural signals the view actually listens to.
    """

    limitChanged = Signal()

    def __init__(self, parent=None):
        """Start with no rows; the page binds `limit` to its revealed count."""
        super().__init__(parent)
        self._limit = 0

    # -- source ------------------------------------------------------------

    def setSourceModel(self, model) -> None:
        """Set the source and follow its structural changes."""
        previous = self.sourceModel()
        if previous is not None:
            for signal, slot in (
                (previous.rowsInserted, self._rows_inserted),
                (previous.rowsRemoved, self._rows_removed),
                (previous.modelReset, self._model_reset),
                (previous.layoutChanged, self._layout_changed),
                (previous.dataChanged, self._data_changed),
            ):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        super().setSourceModel(model)
        if model is not None:
            model.rowsInserted.connect(self._rows_inserted)
            model.rowsRemoved.connect(self._rows_removed)
            model.modelReset.connect(self._model_reset)
            model.layoutChanged.connect(self._layout_changed)
            model.dataChanged.connect(self._data_changed)

    def _rows_inserted(self, _parent, _first, _last) -> None:
        """A new entry shifts the window's contents; reset rather than guess."""
        self.beginResetModel()
        self.endResetModel()

    def _rows_removed(self, _parent, _first, _last) -> None:
        self.beginResetModel()
        self.endResetModel()

    def _model_reset(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    def _layout_changed(self, *_args) -> None:
        """The search proxy re-filtered: the visible rows are a different set."""
        self.beginResetModel()
        self.endResetModel()

    def _data_changed(self, top_left, bottom_right, roles) -> None:
        """Forward one row's data change while it is inside the window."""
        first = max(0, top_left.row())
        last = min(self.rowCount() - 1, bottom_right.row())
        if first <= last:
            self.dataChanged.emit(
                self.index(first, 0), self.index(last, 0), roles
            )

    # -- limit -------------------------------------------------------------

    def _get_limit(self) -> int:
        return self._limit

    def _set_limit(self, limit: int) -> None:
        limit = max(0, int(limit))
        if limit == self._limit:
            return
        old_count = self.rowCount()
        self._limit = limit
        new_count = self.rowCount()
        if new_count > old_count:
            self.beginInsertRows(QModelIndex(), old_count, new_count - 1)
            self.endInsertRows()
        elif new_count < old_count:
            self.beginRemoveRows(QModelIndex(), new_count, old_count - 1)
            self.endRemoveRows()
        self.limitChanged.emit()

    limit = Property(int, _get_limit, _set_limit, notify=limitChanged)

    # -- QAbstractProxyModel ------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        source = self.sourceModel()
        if parent.isValid() or source is None:
            return 0
        return min(self._limit, source.rowCount())

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() or self.sourceModel() is None else 1

    def index(self, row: int, column: int = 0, parent=QModelIndex()) -> QModelIndex:
        if (parent.isValid() or column != 0
                or not 0 <= row < self.rowCount()):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, index) -> QModelIndex:
        return QModelIndex()

    def mapToSource(self, proxy_index: QModelIndex) -> QModelIndex:
        if not proxy_index.isValid() or proxy_index.row() >= self.rowCount():
            return QModelIndex()
        source = self.sourceModel()
        if source is None:
            return QModelIndex()
        return source.index(proxy_index.row(), proxy_index.column())

    def mapFromSource(self, source_index: QModelIndex) -> QModelIndex:
        if not source_index.isValid() or source_index.row() >= self.rowCount():
            return QModelIndex()
        return self.index(source_index.row(), source_index.column())

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        source_index = self.mapToSource(index)
        if not source_index.isValid():
            return None
        return self.sourceModel().data(source_index, role)

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:
        source_index = self.mapToSource(index)
        if not source_index.isValid():
            return False
        return self.sourceModel().setData(source_index, value, role)

    def flags(self, index: QModelIndex):
        source_index = self.mapToSource(index)
        if not source_index.isValid():
            return Qt.NoItemFlags
        return self.sourceModel().flags(source_index)

    def roleNames(self) -> dict:
        source = self.sourceModel()
        return source.roleNames() if source is not None else {}
