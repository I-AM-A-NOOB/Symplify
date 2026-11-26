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

from ..brackets import pair_at
from ..code_style import (
    Style,
    bracket_color_for_layer,
    color_for,
    mask_strings,
    spans,
)
from ..indent_rainbow import spans as indent_spans
from ..worker_protocol import ParsePolicy

#: ``(start_in_block, length, format)`` — what one block has to paint.
BlockFormat = tuple[int, int, QTextCharFormat]

#: How strongly the active bracket pair is filled. The pair keeps its own
#: rainbow colour, tinted rather than replaced, so the box agrees with the
#: brackets around it. VS Code's own `editorBracketMatch.background` is a
#: translucent fill too; a border cannot be expressed by `QTextCharFormat`.
BRACKET_MATCH_ALPHA = 0.18

#: How strong one indent-rainbow level is. Subtle on purpose: the glyphs are the
#: content, the tint only answers "which nesting level is this".
INDENT_ALPHA = 0.10

#: What the highlighter asks for the current name -> value scope.
ScopeProvider = Callable[[], Mapping[str, Any]]

#: What the highlighter asks for the live parser profile.
PolicyProvider = Callable[[], ParsePolicy]


class CodeHighlighter(QSyntaxHighlighter):
    """Paints every span :func:`code_style.spans` reports."""

    def __init__(
        self,
        document: QTextDocument,
        scope_provider: ScopeProvider | None = None,
        styles: Mapping[Style, str] | None = None,
        bracket_colors: Sequence[str] | None = None,
        policy_provider: PolicyProvider | None = None,
        indent_rainbow: bool = True,
    ):
        super().__init__(document)
        self._scope_provider = scope_provider
        self._policy_provider = policy_provider
        # Stored as given: `color_for` owns the fallbacks (None/empty -> the
        # default palette or the bracket rainbow), so there is one such rule.
        self._styles = styles
        self._bracket_colors = bracket_colors
        self._indent_rainbow = bool(indent_rainbow)
        #: Caret position for the active-pair box, or None when the editor is
        #: not focused.
        self._cursor: int | None = None
        self._formats: dict[int, list[BlockFormat]] = {}
        self._cache: dict[tuple, QTextCharFormat] = {}
        self._recomputing = False
        document.contentsChanged.connect(self._on_contents_changed)
        self._recompute()

    def set_palette(
        self,
        styles: Mapping[Style, str] | None,
        bracket_colors: Sequence[str] | None,
    ) -> bool:
        """Recolour an attached highlighter in place; did anything change?

        The document outlives a theme switch unless RinUI recreates the page, so
        a highlighter attached with the old palette would keep painting it —
        this is what the live theme-change handler calls. The format cache is
        cleared because it is keyed by colour, and the old palette's entries
        would otherwise accumulate across switches.

        Returns ``False`` when the palette was already current, which lets the
        caller decide whether a separate :meth:`refresh` (for a parser-policy
        change) is needed instead of recomputing twice.
        """
        if styles == self._styles and bracket_colors == self._bracket_colors:
            return False
        self._styles = styles
        self._bracket_colors = bracket_colors
        self._cache.clear()
        self._recompute()
        return True

    def refresh(self) -> None:
        """Recompute the spans with the live scope and parser policy.

        A settings change (a parser switch, or a variable write) moves what the
        same text should look like without touching the document, so the usual
        ``contentsChanged`` path never runs. The formats are keyed by colour,
        so the cache survives; only the span list is rebuilt.
        """
        self._recompute()

    def set_cursor(self, position: int | None) -> None:
        """Move the active-pair box; ``None`` clears it (editor lost focus).

        Called from QML on ``cursorPositionChanged``. The whole span list is
        recomputed rather than just the pair: the text is short, and one path
        keeps the box correct when an edit moved the brackets underneath the
        caret.
        """
        if position is not None:
            position = max(0, position)
        if position == self._cursor:
            return
        self._cursor = position
        self._recompute()

    def set_indent_rainbow(self, enabled: bool) -> bool:
        """Turn the indent tint on/off; did anything change?"""
        enabled = bool(enabled)
        if enabled == self._indent_rainbow:
            return False
        self._indent_rainbow = enabled
        self._recompute()
        return True

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
            policy = (
                None if self._policy_provider is None else self._policy_provider()
            )
            text = document.toPlainText()
            masked = mask_strings(text)
            pair = None
            if self._cursor is not None:
                pair = pair_at(masked, min(self._cursor, len(text)))

            formatted: list[tuple[int, int, QTextCharFormat]] = []
            for span in spans(text, scope, policy):
                color = color_for(span, self._styles, self._bracket_colors)
                if color is None:
                    continue            # the palette leaves this one to the control
                unmatched = span.style is Style.BRACKET and span.layer is None
                background = None
                if pair is not None and span.start in pair:
                    background = self._tint(color, BRACKET_MATCH_ALPHA)
                formatted.append(
                    (
                        span.start,
                        span.length,
                        self._format_for(color, unmatched, background),
                    )
                )

            if self._indent_rainbow:
                for start, length, level in indent_spans(masked):
                    base = bracket_color_for_layer(level, self._bracket_colors)
                    formatted.append(
                        (start, length, self._background_format(base))
                    )

            formatted.sort(key=lambda item: item[0])
            per_block: dict[int, list[BlockFormat]] = {}
            for start, length, fmt in formatted:
                block = document.findBlock(start)
                if not block.isValid():
                    continue
                # A span may cross blocks: a triple-quoted string is one token
                # that can hold newlines. `setFormat` paints one block only, so
                # split it at each block boundary instead of letting the tail
                # fall off the first block.
                remaining = length
                position = start
                while remaining > 0 and block.isValid():
                    offset = position - block.position()
                    take = min(remaining, max(0, block.length() - offset))
                    if take == 0:
                        block = block.next()
                        continue
                    per_block.setdefault(block.blockNumber(), []).append(
                        (offset, take, fmt)
                    )
                    remaining -= take
                    position += take
                    block = block.next()
            self._formats = per_block
            self.rehighlight()          # re-runs highlightBlock for every block
        finally:
            self._recomputing = False

    @staticmethod
    def _tint(color: str, alpha: float) -> QColor:
        """``color`` at ``alpha``, for a fill behind glyphs.

        The pair box and the indent levels use the bracket rainbow itself, so a
        tinted level and the bracket that opened it cannot disagree about which
        colour level it is.
        """
        tint = QColor(color)
        tint.setAlphaF(alpha)
        return tint

    def _format_for(
        self,
        color: str,
        underline: bool = False,
        background: QColor | None = None,
    ) -> QTextCharFormat:
        """One format per (colour, underline, background) — shared, not per key."""
        key = (
            color,
            bool(underline),
            background.name(QColor.NameFormat.HexArgb) if background else "",
        )
        fmt = self._cache.get(key)
        if fmt is None:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if underline:
                fmt.setFontUnderline(True)
            if background is not None:
                fmt.setBackground(background)
            self._cache[key] = fmt
        return fmt

    def _background_format(self, color: str) -> QTextCharFormat:
        """A fill with no foreground, for an indent level."""
        tint = self._tint(color, INDENT_ALPHA)
        key = ("indent", tint.name(QColor.NameFormat.HexArgb))
        fmt = self._cache.get(key)
        if fmt is None:
            fmt = QTextCharFormat()
            fmt.setBackground(tint)
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
    policy_provider: PolicyProvider | None = None,
    indent_rainbow: bool = True,
) -> CodeHighlighter:
    """Code colouring for a QML text item's ``textDocument`` property.

    QML hands over a ``QQuickTextDocument``, whose ``textDocument()`` is the
    ``QTextDocument`` the item edits. The highlighter is parented to *that
    document* rather than to a viewmodel: RinUI rebuilds every page on
    navigation, so the document is what knows when this instance is done — and
    that rebuild is also what re-applies a changed palette.

    Both providers are asked on every recompute, so a variable write or a parser
    switch is reflected without the caller handing over a new snapshot.
    """
    document = text_document.textDocument()
    highlighter = CodeHighlighter(
        document,
        scope_provider,
        styles,
        bracket_colors,
        policy_provider,
        indent_rainbow,
    )
    highlighter.setParent(document)
    return highlighter
