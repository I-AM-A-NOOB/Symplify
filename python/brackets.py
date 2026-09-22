# coding: utf-8
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
from typing import Dict, List, Optional, Sequence, Tuple

#: Bracket pairs — the ones the v1 app highlighted. Single characters: the
#: pairing below walks the string one character at a time.
DEFAULT_PAIRS: Dict[str, str] = {"(": ")", "[": "]", "{": "}"}

#: One colour per nesting depth, cycled. The v1 palette, and also what the
#: ``custom`` bracket mode starts from and is repaired to. Kept in the canonical
#: form ``parse_colors`` produces (lower case hex), so the settings default, the
#: stored string and this tuple are the same value rather than three spellings of
#: it.
DEFAULT_COLORS: Tuple[str, ...] = (
    "#ff6b6b",
    "#ff9f43",
    "#ffd93d",
    "#6bcb77",
    "#4d96ff",
    "#9b5de5",
)

#: One entry of a custom palette: ``#rrggbb``.
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def parse_colors(text: str) -> Tuple[str, ...]:
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
Span = Tuple[int, int, Optional[int]]


def spans(
    text: str,
    pairs: Dict[str, str] = DEFAULT_PAIRS,
    layers: int = len(DEFAULT_COLORS),
) -> List[Span]:
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
    stack: List[Tuple[int, str]] = []           # (start, bracket)
    matched: List[Tuple[int, int]] = []         # (opening start, closing start)
    errors: List[int] = []

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
    depth: Dict[int, int] = {}
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

    result: List[Span] = []
    for order, (opening_start, closing_start) in enumerate(matched):
        layer = depth[order] % layers
        result.append((opening_start, 1, layer))
        result.append((closing_start, 1, layer))
    result.extend((start, 1, None) for start in errors)
    result.sort()
    return result
