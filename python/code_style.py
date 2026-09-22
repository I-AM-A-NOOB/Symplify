# coding: utf-8
"""What a piece of code should look like (pure Python, zero Qt).

The one place that turns text into *colour spans*. Two renderers consume the
same spans, so the editable code inputs and the places that merely display an
expression can never drift apart:

* ``viewmodel/highlighter.py`` — a ``QSyntaxHighlighter``, for the
  ``QTextDocument`` behind the editable inputs;
* :func:`to_rich_text` — markup, for a read-only ``Text`` item.

The spans have two producers, merged here: ``model/lexer.py`` says what each run
of characters *is*, and ``brackets.py`` adds the nesting layer that colours the
brackets. Brackets win where the two overlap, which is why the merge is a single
function instead of something each renderer repeats.

Anything that colours code — now or later, Pygments included — contributes
spans to this list rather than painting on its own. A second painter would lose:
``QSyntaxHighlighter.setFormat`` is last-write-wins per range, so two
highlighters on one document silently erase each other.
"""

import html
from enum import Enum, auto
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from . import code_themes
from .brackets import DEFAULT_COLORS as BRACKET_COLORS
from .brackets import spans as bracket_spans
from .model.lexer import TokenKind, tokenize


class Style(Enum):
    """What a span means, for rendering.

    Every classified run gets a member; whether it ends up *painted* is the
    palette's call, and :func:`color_for` returns ``None`` for a style the
    palette leaves out — which is how One Light keeps its operators bare (its
    ``keyword.operator`` is the default ink) while One Dark colours them.
    """

    NUMBER = auto()
    VARIABLE = auto()
    CALLABLE = auto()
    CONSTANT = auto()
    OPERATOR = auto()
    UNKNOWN = auto()
    BRACKET = auto()


class CodeSpan(NamedTuple):
    """``(start, length, style)``, plus the bracket layer when there is one."""

    start: int
    length: int
    style: Style
    layer: Optional[int] = None


#: Which token kinds are worth a span of their own.
_KIND_STYLES: Dict[TokenKind, Style] = {
    TokenKind.NUMBER: Style.NUMBER,
    TokenKind.VARIABLE: Style.VARIABLE,
    TokenKind.CALLABLE: Style.CALLABLE,
    TokenKind.CONSTANT: Style.CONSTANT,
    TokenKind.OPERATOR: Style.OPERATOR,
    TokenKind.UNKNOWN: Style.UNKNOWN,
}

def theme(family: str, dark: bool) -> Tuple[Mapping[Style, str], Tuple[str, ...]]:
    """The palette and bracket colours for a family at the active UI theme.

    Every family in ``code_themes`` has a dark and a light member, so the code
    colours follow the app's theme: Atom One is One Dark on a dark UI and One
    Light on a light one.

    Returns:
        ``(styles, bracket_colors)``. The bracket colours are the family's own
        ``editorBracketHighlight`` list, or — when it names none, which is the
        case for most of them — VS Code's registered defaults for that kind, so
        "follow the code theme" behaves the way it does in VS Code rather than
        dropping to a palette of our own. The list is always non-empty, and the
        nesting levels cycle through it (``brackets.parse_colors`` reads a
        *custom* list; ``code_style.color_for`` owns the last-resort fallback for
        callers that pass no palette at all). An unknown family falls back to
        :data:`DEFAULT_STYLES` rather than raising: a settings file can name a
        family this build does not have.
    """
    layer = code_themes.THEMES.get(family, {}).get("dark" if dark else "light")
    if layer is None:
        return DEFAULT_STYLES, code_themes.VSCODE_BRACKET_COLORS[
            "dark" if dark else "light"
        ]

    styles = {
        _STYLE_BY_NAME[name]: color
        for name, color in layer["styles"].items()
        if name in _STYLE_BY_NAME
    }
    brackets = tuple(layer["brackets"]) or code_themes.VSCODE_BRACKET_COLORS[
        "dark" if dark else "light"
    ]
    return styles, brackets


def surface(family: str, dark: bool) -> Tuple[str, str, str]:
    """The family's ``(background, ink, placeholder)`` for a code input.

    Any of them may be ``""``, which means the family has nothing to say — High
    Contrast Light states no ``editor.background`` at all, and a family that names
    no surface gets no placeholder either — and the control keeps the UI theme's
    own colours. The rule matches the bracket palette's: absence is not a value,
    and it is the consumer that supplies the fallback.
    """
    layer = code_themes.THEMES.get(family, {}).get("dark" if dark else "light")
    if layer is None:
        return "", "", ""
    return layer["background"], layer["ink"], layer["placeholder"]


#: ``"number" -> Style.NUMBER``: how ``code_themes`` names the styles.
_STYLE_BY_NAME: Dict[str, Style] = {style.name.lower(): style for style in Style}

#: Style -> colour, used when the theme cannot answer — an unknown family, or a
#: caller with no palette at all (headless, tests). **Only what is unambiguous**:
#: numbers, names, callables and constants are left to the control's own text
#: colour, because a fixed colour cannot read on both themes and the bracket
#: rainbow already occupies the hue wheel.
DEFAULT_STYLES: Dict[Style, str] = {
    Style.UNKNOWN: "#ff0000",       # a character the language has no use for
}


def spans(text: str, scope: Optional[Mapping[str, Any]] = None) -> List[CodeSpan]:
    """Everything in ``text`` worth painting, in order.

    Args:
        text: The expression.
        scope: Name -> value, so a stored variable colours differently from a
            free symbol.

    Returns:
        The merged spans: lexer styles first, brackets last, ordered by start so
        that a bracket lands on top of the punctuation it belongs to.
    """
    if not text:
        return []

    merged: List[CodeSpan] = []
    for token in tokenize(text, scope):
        style = _KIND_STYLES.get(token.kind)
        if style is not None:
            merged.append(CodeSpan(token.start, token.length, style))

    merged.extend(
        CodeSpan(start, length, Style.BRACKET, layer)
        for start, length, layer in bracket_spans(text)
    )
    merged.sort(key=lambda span: span.start)
    return merged


def color_for(
    span: CodeSpan,
    styles: Optional[Mapping[Style, str]] = None,
    bracket_colors: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """The colour a span is painted with, or None to leave it to the control.

    Both renderers ask this, so neither can invent a colour of its own — and a
    style the palette does not mention is simply not painted. ``bracket_colors``
    follows the same rule as ``styles``: ``None`` — or the empty tuple a family
    with no ``editorBracketHighlight`` gives — means "no opinion", and
    ``brackets.DEFAULT_COLORS`` stands in. Treating an empty tuple as a palette of
    zero colours is what once divided by zero here; because that happened inside
    the highlighter's recompute it left the input painted with the *previous*
    text's formats, and every later refresh (typing, pasting, a theme switch) died
    the same way.
    """
    if styles is None:
        styles = DEFAULT_STYLES
    if not bracket_colors:
        bracket_colors = BRACKET_COLORS
    if span.style is not Style.BRACKET:
        return styles.get(span.style)
    if span.layer is None:
        return styles.get(Style.UNKNOWN)     # an unmatched bracket reads as wrong
    return bracket_colors[span.layer % len(bracket_colors)]


def to_rich_text(
    text: str,
    scope: Optional[Mapping[str, Any]] = None,
    styles: Optional[Mapping[Style, str]] = None,
    bracket_colors: Optional[Sequence[str]] = None,
) -> str:
    """``text`` as markup, for the read-only places that show an expression.

    The text is HTML-escaped as it goes — these are expressions, full of ``<``
    and ``&`` — and only the spans get wrapped, so the escaping can never shift
    one.
    """
    if not text:
        return ""

    marked = spans(text, scope)
    if not marked:
        return html.escape(text)

    out: List[str] = []
    cursor = 0
    for span in marked:
        if span.start < cursor:
            continue                        # overlapping span: the earlier wins
        color = color_for(span, styles, bracket_colors)
        if color is None:
            continue                        # nothing to paint it with
        out.append(html.escape(text[cursor:span.start]))
        fragment = html.escape(text[span.start:span.start + span.length])
        out.append(f'<span style="color:{color};">{fragment}</span>')
        cursor = span.start + span.length
    out.append(html.escape(text[cursor:]))
    return "".join(out)
