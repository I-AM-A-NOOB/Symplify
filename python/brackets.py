"""Rainbow bracket pairing (pure Python, zero Qt).

Ported from the QWidget app's ``RainbowBracketsHighlighter`` (v1): brackets are
paired with a stack, a stray bracket is **not allowed to shift the colours** of
the pairs around it, and every bracket takes a layer from its nesting depth so
both ends of a pair always share a colour.

:func:`spans` is the only entry point: ``python/code_style.py`` merges its
output with what ``model/lexer.py`` says the text is, and the renderers work
from those merged spans.
"""

import re

#: Bracket pairs — the ones the v1 app highlighted. Single characters: the
#: pairing below walks the string one character at a time.
DEFAULT_PAIRS: dict[str, str] = {"(": ")", "[": "]", "{": "}"}

#: The reverse map, for matching backwards from a closing bracket.
_CLOSING_TO_OPENING: dict[str, str] = {
    closing: opening for opening, closing in DEFAULT_PAIRS.items()
}


def pair_at(text: str, position: int) -> tuple[int, int] | None:
    """The ``(opening, closing)`` indices of the bracket at/next to ``position``.

    ``position`` is a caret: the character before it is tried first (the one the
    caret just typed or stepped over), then the character at it. Nesting is
    respected across *all* bracket kinds, so ``([)]`` is not a pair; an
    unmatched bracket answers ``None`` and keeps its existing error colour.

    Callers pass text with string contents blanked (``code_style.mask_strings``):
    a bracket inside a quoted literal is data and must not pair.
    """
    if not text:
        return None
    position = max(0, min(position, len(text)))

    for probe in (position - 1, position):
        if not 0 <= probe < len(text):
            continue
        char = text[probe]
        if char in DEFAULT_PAIRS:
            pair = _match_forward(text, probe)
        elif char in _CLOSING_TO_OPENING:
            pair = _match_backward(text, probe)
        else:
            continue
        if pair is not None:
            return pair
    return None


def _match_forward(text: str, start: int) -> tuple[int, int] | None:
    stack: list[str] = []
    for index in range(start, len(text)):
        char = text[index]
        if char in DEFAULT_PAIRS:
            stack.append(DEFAULT_PAIRS[char])
        elif char in _CLOSING_TO_OPENING:
            if not stack or stack[-1] != char:
                return None
            stack.pop()
            if not stack:
                return (start, index)
    return None


def _match_backward(text: str, start: int) -> tuple[int, int] | None:
    stack: list[str] = []
    for index in range(start, -1, -1):
        char = text[index]
        if char in _CLOSING_TO_OPENING:
            stack.append(_CLOSING_TO_OPENING[char])
        elif char in DEFAULT_PAIRS:
            if not stack or stack[-1] != char:
                return None
            stack.pop()
            if not stack:
                return (index, start)
    return None


#: One colour per nesting depth, cycled. The v1 palette, and also what the
#: ``custom`` bracket mode starts from and is repaired to. Kept in the canonical
#: form ``parse_colors`` produces (lower case hex), so the settings default, the
#: stored string and this tuple are the same value rather than three spellings of
#: it.
DEFAULT_COLORS: tuple[str, ...] = (
    "#ff6b6b",
    "#ff9f43",
    "#ffd93d",
    "#6bcb77",
    "#4d96ff",
    "#9b5de5",
)

#: One entry of a custom palette: ``#rrggbb``.
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def parse_colors(text: str) -> tuple[str, ...]:
    """The custom palette in ``text``: comma-separated ``#rrggbb``, normalised.

    Entries that are not a ``#rrggbb`` colour are dropped rather than rejecting
    the whole line, so a list someone is still typing keeps whatever is usable;
    an empty result means "no usable colours", which the caller reads as "no
    opinion" and falls back from.
    """
    if not text:
        return ()
    return tuple(
        entry.strip().lower()
        for entry in text.split(",")
        if _HEX_COLOR.match(entry.strip())
    )

#: What an unmatched bracket is painted with.
ERROR_COLOR = "#ff0000"

#: ``(start, length, layer)`` — ``layer`` is ``None`` for an unmatched bracket.
Span = tuple[int, int, int | None]


def spans(
    text: str,
    pairs: dict[str, str] = DEFAULT_PAIRS,
    layers: int = len(DEFAULT_COLORS),
) -> list[Span]:
    """Every bracket in ``text`` as ``(start, length, layer)``, in order.

    ``layer`` is ``None`` for a bracket that never gets a partner — a stray
    closing bracket, or an opening one still unclosed at the end. Those are what
    the callers paint as errors.
    """
    if not text:
        return []

    closing_to_opening = {closing: opening for opening, closing in pairs.items()}
    layers = max(1, layers)

    # Pass 1: match what can be matched and remember the strays. Keeping the
    # strays out of `matched` is what stops them from shifting the layers.
    stack: list[tuple[int, str]] = []           # (start, bracket)
    matched: list[tuple[int, int]] = []         # (opening start, closing start)
    errors: list[int] = []

    for index, char in enumerate(text):
        if char in pairs:
            stack.append((index, char))
        elif char in closing_to_opening:
            if stack and pairs[stack[-1][1]] == char:
                opening_start, _ = stack.pop()
                matched.append((opening_start, index))
            else:
                errors.append(index)            # closing bracket with no opener
    errors.extend(start for start, _ in stack)  # openings that never closed

    # Pass 2: the depth of a pair is how many pairs enclose it, counted among the
    # matched ones only — so the outermost pair is layer 0.
    depth: dict[int, int] = {}
    open_count = 0
    for _, kind, order in sorted(
        [(open_start, 0, order) for order, (open_start, _) in enumerate(matched)]
        + [(close_start, 1, order) for order, (_, close_start) in enumerate(matched)]
    ):
        if kind == 0:
            depth[order] = open_count
            open_count += 1
        else:
            open_count -= 1

    result: list[Span] = []
    for order, (opening_start, closing_start) in enumerate(matched):
        layer = depth[order] % layers
        result.append((opening_start, 1, layer))
        result.append((closing_start, 1, layer))
    result.extend((start, 1, None) for start in errors)
    result.sort()
    return result
