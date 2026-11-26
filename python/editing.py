"""Editor mechanics for the code inputs (pure Python, zero Qt, zero SymPy).

The QML text controls own the caret, the selection and the undo stack; this
module owns *what a key should change*, so the rules are testable without a
window and every input (the Calculator's Code box, the Assign value, the
Variables expression editor) behaves the same.

Every answer is one :class:`Edit`: one contiguous replacement, applied in one
call. That is what keeps a pair ``()``, a wrapped selection or a multi-line
indent a single undo step — the QML side never has to know how to group edits.
A ``None`` answer means "the control's own handling is right" (a plain
character, a lone closing bracket, Backspace on a normal character).

Strings are data, not source: the lexer decides whether the caret is inside a
quoted literal, and there a bracket or quote is inserted literally instead of
opening a pair. The table cell's inline editor is deliberately not wired to
this module — its Return/Escape contract belongs to the view.
"""

from dataclasses import dataclass

from .lexer import TokenKind, tokenize

#: What one action key inserts. Quotes pair with themselves.
OPEN_TO_CLOSE: dict[str, str] = {"(": ")", "[": "]", "{": "}", "'": "'", '"': '"'}
CLOSERS = frozenset((")", "]", "}"))
QUOTES = frozenset(("'", '"'))

#: The indent one Tab adds; Python's own four spaces.
INDENT = "    "


@dataclass(frozen=True)
class Edit:
    """One replacement and where the selection goes afterwards.

    ``text`` replaces ``[replace_start, replace_end)``; the QML caller does
    ``remove`` + ``insert`` and then ``select``. An empty replacement with
    ``replace_start == replace_end`` is a pure caret move (skip over a closing
    bracket).
    """

    replace_start: int
    replace_end: int
    text: str
    selection_start: int
    selection_end: int


def _inside_string(text: str, position: int) -> bool:
    """Is ``position`` inside a quoted literal (including an open one's end)?"""
    for token in tokenize(text):
        if token.kind is not TokenKind.STRING:
            continue
        end = token.start + token.length
        if token.start < position < end:
            return True
        # An unterminated string runs to the end of the text: a quote typed
        # there closes it instead of starting an empty pair.
        if token.invalid and position == end:
            return True
    return False


def insert_char(text: str, start: int, end: int, char: str) -> Edit | None:
    """Opening a pair, closing it, wrapping a selection, or typing a quote.

    Returns ``None`` when the control should insert the character itself.
    """
    if char in OPEN_TO_CLOSE:
        closing = OPEN_TO_CLOSE[char]
        if start != end:
            if _inside_string(text, start) or _inside_string(text, end):
                return None
            selected = text[start:end]
            return Edit(
                start, end, char + selected + closing, start + 1, end + 1
            )
        if _inside_string(text, start):
            if start < len(text) and text[start] == char:
                # The closing quote is already there: step over it.
                return Edit(start, start, "", start + 1, start + 1)
            return Edit(start, start, char, start + 1, start + 1)
        return Edit(start, start, char + closing, start + 1, start + 1)

    if char in CLOSERS:
        if start != end:
            return None
        if start < len(text) and text[start] == char:
            # A closing bracket the user just opened: step over it.
            return Edit(start, start, "", start + 1, start + 1)
        return None

    return None


def backspace(text: str, start: int, end: int) -> Edit | None:
    """Delete an empty pair together, like every code editor does."""
    if start != end or start == 0:
        return None
    previous = text[start - 1]
    closing = OPEN_TO_CLOSE.get(previous)
    if closing is None or start >= len(text) or text[start] != closing:
        return None
    return Edit(start - 1, start + 1, "", start - 1, start - 1)


def newline(text: str, start: int, end: int, unit: str = INDENT) -> Edit:
    """Enter: keep the current indentation, and open a block between a pair.

    ``f(|)`` becomes three lines with the caret on the indented middle one;
    everywhere else the new line carries the current line's leading whitespace
    plus one level when the caret follows an opening bracket.
    """
    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[line_start:start]
    indent = prefix[:len(prefix) - len(prefix.lstrip(" \t"))]

    if start == end and start > 0 and start < len(text):
        opening = text[start - 1]
        closing = OPEN_TO_CLOSE.get(opening)
        if closing is not None and text[start] == closing:
            inner = indent + unit
            inserted = "\n" + inner + "\n" + indent
            caret = start + 1 + len(inner)
            return Edit(start, start, inserted, caret, caret)

    extra = unit if start > 0 and text[start - 1] in OPEN_TO_CLOSE else ""
    inserted = "\n" + indent + extra
    caret = start + len(inserted)
    return Edit(start, end, inserted, caret, caret)


def _outdent_len(line: str, unit: str) -> int:
    """How many leading characters one outdent removes from ``line``."""
    if line.startswith("\t"):
        return 1
    spaces = len(line) - len(line.lstrip(" "))
    return min(spaces, len(unit))


def indent(
    text: str,
    start: int,
    end: int,
    outdent: bool = False,
    unit: str = INDENT,
) -> Edit | None:
    """Indent or outdent the touched lines; ``None`` when nothing would move.

    A caret with no selection works on its own line; a selection works on every
    line it touches, and a selection ending exactly at a line start does not
    touch that next line. The selection is carried through the shifts.
    """
    if start == end:
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", start)
        if line_end < 0:
            line_end = len(text)
        line = text[line_start:line_end]
        if outdent:
            removed = _outdent_len(line, unit)
            if removed == 0:
                return None
            return Edit(
                line_start,
                line_start + removed,
                "",
                max(0, start - removed),
                max(0, end - removed),
            )
        return Edit(
            line_start, line_start, unit, start + len(unit), end + len(unit)
        )

    last_position = end - 1 if end > start else start
    first_line = text.rfind("\n", 0, start) + 1
    last_line = text.rfind("\n", 0, last_position) + 1
    block_end = text.find("\n", last_line)
    if block_end < 0:
        block_end = len(text)

    line_starts = [first_line]
    while True:
        following = text.find("\n", line_starts[-1])
        if following < 0 or following + 1 > last_line:
            break
        line_starts.append(following + 1)

    deltas: list[int] = []
    pieces: list[str] = []
    for line_start in line_starts:
        line_end = text.find("\n", line_start)
        if line_end < 0 or line_end > block_end:
            line_end = block_end
        line = text[line_start:line_end]
        if outdent:
            removed = _outdent_len(line, unit)
            deltas.append(-removed)
            pieces.append(line[removed:])
        else:
            deltas.append(len(unit))
            pieces.append(unit + line)

    if all(delta == 0 for delta in deltas):
        return None

    # A selection that starts exactly at a line start keeps that edge *before*
    # the indentation it just added, so it still covers the whole line (VS
    # Code's behaviour); a bare caret moves past the inserted indent.
    if start != end:
        new_start = start + sum(
            delta for line_start, delta in zip(line_starts, deltas)
            if line_start < start
        )
    else:
        new_start = start + sum(
            delta for line_start, delta in zip(line_starts, deltas)
            if line_start <= start
        )
    new_end = end + sum(deltas)
    return Edit(
        first_line,
        block_end,
        "\n".join(pieces),
        new_start,
        new_end,
    )


def apply(
    text: str,
    start: int,
    end: int,
    action: str,
    unit: str = INDENT,
) -> Edit | None:
    """The edit ``action`` asks for, or ``None`` to let the control handle it.

    Args:
        text: The editor's whole text.
        start: Selection start (also the caret when ``start == end``).
        end: Selection end.
        action: A character to insert (``"("``, ``")"``, ``'"'`` …) or one of
            ``"backspace"``, ``"tab"``, ``"outdent"``, ``"return"``.
        unit: One indentation level.
    """
    length = len(text)
    start = max(0, min(start, length))
    end = max(0, min(end, length))
    if start > end:
        start, end = end, start

    if action in OPEN_TO_CLOSE or action in CLOSERS:
        return insert_char(text, start, end, action)
    if action == "backspace":
        return backspace(text, start, end)
    if action == "tab":
        return indent(text, start, end, unit=unit)
    if action == "outdent":
        return indent(text, start, end, outdent=True, unit=unit)
    if action == "return":
        return newline(text, start, end, unit=unit)
    return None


__all__ = [
    "CLOSERS",
    "Edit",
    "INDENT",
    "OPEN_TO_CLOSE",
    "QUOTES",
    "apply",
    "backspace",
    "indent",
    "insert_char",
    "newline",
]
