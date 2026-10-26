"""Painting code in the QML text items.

QML has no ``QSyntaxHighlighter``, but ``TextArea.textDocument`` hands out the
``QTextDocument`` the item edits — the same document the QWidget app attached
its highlighter to. *What* to paint comes from ``python/code_style.py``, so this
module only turns spans into ``QTextCharFormat``; the lexical rules, the
palettes and the bracket layers live there and stay Qt-free.

Pairs are matched across the whole document, not per block: an expression may be
typed over several lines, and a bracket closed on the next one has to keep its
partner's colour (``highlightBlock`` only ever sees one block). That is why the
spans for the whole text are recomputed and the document rehighlighted, rather
than only the block that changed.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PySide6.QtQuick import QQuickTextDocument

from ..code_style import Style, color_for, spans

#: ``(start_in_block, length, format)`` — what one block has to paint.
BlockFormat = tuple[int, int, QTextCharFormat]

#: What the highlighter asks for the current name -> value scope.
ScopeProvider = Callable[[], Mapping[str, Any]]


class CodeHighlighter(QSyntaxHighlighter):
    """Paints every span :func:`code_style.spans` reports."""

    def __init__(
        self,
        document: QTextDocument,
        scope_provider: ScopeProvider | None = None,
        styles: Mapping[Style, str] | None = None,
        bracket_colors: Sequence[str] | None = None,
    ):
        super().__init__(document)
        self._scope_provider = scope_provider
        # Stored as given: `color_for` owns the fallbacks (None/empty -> the
        # default palette or the bracket rainbow), so there is one such rule.
        self._styles = styles
        self._bracket_colors = bracket_colors
        self._formats: dict[int, list[BlockFormat]] = {}
        self._cache: dict[str, QTextCharFormat] = {}
        self._recomputing = False
        document.contentsChanged.connect(self._on_contents_changed)
        self._recompute()

    def set_palette(
        self,
        styles: Mapping[Style, str] | None,
        bracket_colors: Sequence[str] | None,
    ) -> None:
        """Recolour an attached highlighter in place.

        The document outlives a theme switch unless RinUI recreates the page, so
        a highlighter attached with the old palette would keep painting it —
        this is what the live theme-change handler calls. The format cache is
        cleared because it is keyed by colour, and the old palette's entries
        would otherwise accumulate across switches.
        """
        if styles == self._styles and bracket_colors == self._bracket_colors:
            return
        self._styles = styles
        self._bracket_colors = bracket_colors
        self._cache.clear()
        self._recompute()

    def _on_contents_changed(self) -> None:
        # setFormat can make the document emit this again, so ignore it while the
        # recompute (and the rehighlight it ends with) is running.
        if self._recomputing:
            return
        self._recompute()

    def _recompute(self) -> None:
        self._recomputing = True
        try:
            document = self.document()
            scope = None if self._scope_provider is None else self._scope_provider()
            per_block: dict[int, list[BlockFormat]] = {}
            for span in spans(document.toPlainText(), scope):
                block = document.findBlock(span.start)
                if not block.isValid():
                    continue
                color = color_for(span, self._styles, self._bracket_colors)
                if color is None:
                    continue            # the palette leaves this one to the control
                unmatched = span.style is Style.BRACKET and span.layer is None
                per_block.setdefault(block.blockNumber(), []).append(
                    (
                        span.start - block.position(),
                        span.length,
                        self._format_for(color, unmatched),
                    )
                )
            self._formats = per_block
            self.rehighlight()          # re-runs highlightBlock for every block
        finally:
            self._recomputing = False

    def _format_for(self, color: str, underline: bool = False) -> QTextCharFormat:
        """One format per (colour, underline) — never a fresh one per keystroke."""
        key = f"{color}|{int(underline)}"
        fmt = self._cache.get(key)
        if fmt is None:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if underline:
                fmt.setFontUnderline(True)
            self._cache[key] = fmt
        return fmt

    def highlightBlock(self, text: str) -> None:
        for start, length, fmt in self._formats.get(self.currentBlock().blockNumber(), ()):
            self.setFormat(start, length, fmt)


def attach(
    text_document: QQuickTextDocument,
    scope_provider: ScopeProvider | None = None,
    styles: Mapping[Style, str] | None = None,
    bracket_colors: Sequence[str] | None = None,
) -> CodeHighlighter:
    """Code colouring for a QML text item's ``textDocument`` property.

    QML hands over a ``QQuickTextDocument``, whose ``textDocument()`` is the
    ``QTextDocument`` the item edits. The highlighter is parented to *that
    document* rather than to a viewmodel: RinUI rebuilds every page on
    navigation, so the document is what knows when this instance is done — and
    that rebuild is also what re-applies a changed palette.
    """
    document = text_document.textDocument()
    highlighter = CodeHighlighter(document, scope_provider, styles, bracket_colors)
    highlighter.setParent(document)
    return highlighter
