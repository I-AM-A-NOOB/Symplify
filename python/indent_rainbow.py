"""Indent-rainbow spans (pure Python, zero Qt).

Each line's leading whitespace is split into indentation units, and each unit
gets a nesting level. The highlighter paints the unit with a faint background
in the level's bracket colour, so a deeply nested, Lisp-style expression reads
its depth even when the brackets are far apart.

This is *not* an indent guide: nothing is drawn between lines. A guide needs an
overlay that follows scrolling and wrapping; colouring the whitespace it already
paints needs no second layer. Blank lines are skipped so an empty line does not
paint a stripe.
"""

Span = tuple[int, int, int]  # (start, length, level)

#: Spaces per indentation level (the same four `editing.INDENT` inserts).
UNIT = 4


def spans(text: str, unit: int = UNIT) -> list[Span]:
    """The leading-whitespace runs of ``text`` as ``(start, length, level)``.

    A tab is one level. Spaces are grouped into units; a short final group is
    still a level of its own (a hand-typed three-space indent should not fall
    back to the previous colour). Only lines that also have content contribute
    — a blank line made of spaces is not a nesting level.
    """
    if not text:
        return []
    unit = max(1, unit)
    result: list[Span] = []
    offset = 0

    for line in text.split("\n"):
        if line.strip():
            whitespace = len(line) - len(line.lstrip(" \t"))
            level = 0
            spaces = 0
            index = 0
            while index < whitespace:
                if line[index] == "\t":
                    if spaces:
                        result.append((offset + index - spaces, spaces, level))
                        level += 1
                        spaces = 0
                    result.append((offset + index, 1, level))
                    level += 1
                else:
                    spaces += 1
                    if spaces == unit:
                        result.append(
                            (offset + index - unit + 1, unit, level)
                        )
                        level += 1
                        spaces = 0
                index += 1
            if spaces:
                result.append((offset + index - spaces, spaces, level))
        offset += len(line) + 1

    return result


__all__ = ["Span", "UNIT", "spans"]
