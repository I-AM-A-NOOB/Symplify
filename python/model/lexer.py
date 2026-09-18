# coding: utf-8
"""Tokenizing the calculator's expression language (pure Python, zero Qt).

The point of this module is that the *lexical* rules live next to the rules that
decide what the text **means** (``calculator.py``), and are read by everything
that has to point at a piece of the text: syntax colouring, hover, completion
and the ranges error messages underline.

What this is not: a parser, and not a judge. It says what each run of characters
*is*, never whether the expression is valid — that stays with ``Calculator``,
which answers with ``Success`` / ``Failure``. Keeping the verdict there is what
stops a highlighter from claiming ``foo(1)`` is a function call while
``unknown_calls`` reports it as an unknown one (``implicit_multiplication``
turns it into ``f*o**2``).

The character classes are Python's own (``str.isidentifier``), because the
parser tokenizes with Python's tokenizer: a name this module accepts is a name
SymPy can resolve, and ``x²`` splits into a name and a stray character instead
of looking like one identifier.
"""

from enum import Enum, auto
from typing import Any, List, Mapping, NamedTuple, Optional, Sequence

from .variable import SYMPY_CONSTANTS, sympy_callables


class TokenKind(Enum):
    """What a run of characters is.

    Attributes:
        NUMBER: An integer, float or hex/octal/binary literal.
        NAME: A bare name. Unknown names stay *symbolic* — that is the
            documented permissiveness, not an error.
        VARIABLE: A name that resolves to a stored variable.
        CALLABLE: A name SymPy resolves as a function.
        CONSTANT: A name SymPy resolves as a constant (``pi``, ``E``, ...).
        OPERATOR: An operator or separator (``+``, ``**``, ``,``, ``.`` ...).
        BRACKET: One of ``()[]{}``.
        SPACE: Whitespace, kept so callers can tell text apart without gaps.
        UNKNOWN: A character the expression language has no use for.
    """

    NUMBER = auto()
    NAME = auto()
    VARIABLE = auto()
    CALLABLE = auto()
    CONSTANT = auto()
    OPERATOR = auto()
    BRACKET = auto()
    SPACE = auto()
    UNKNOWN = auto()


class Token(NamedTuple):
    """``(start, length, kind)`` — a tuple, so it is also a colour span."""

    start: int
    length: int
    kind: TokenKind


#: Multi-character first, so ``**`` never lexes as two ``*``. Mirrors what the
#: parser accepts: ``convert_xor`` makes ``^`` a power, and the augmented forms
#: come from ``calculator.AUGMENTED_OPS``.
_OPERATORS: Sequence[str] = (
    "**=", "//=", ">>=", "<<=", "!=", "<=", ">=", "==",
    "**", "//", "<<", ">>",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "+", "-", "*", "/", "%", "^", "=", "<", ">", "~", "&", "|", "@",
    ",", ".", ":", ";",
)

_BRACKETS = frozenset("()[]{}")


def _is_name_start(char: str) -> bool:
    """A character a Python identifier may start with (``λ`` and ``_`` count)."""
    return char.isidentifier()


def _is_name_continue(char: str) -> bool:
    """A character a Python identifier may continue with.

    Asked of Python rather than ``isalnum()`` on purpose: ``isalnum`` accepts
    superscripts and fractions, which no identifier may hold.
    """
    return ("a" + char).isidentifier()


def _scan_number(text: str, start: int) -> int:
    """Index just past the numeric literal at ``start``.

    ``isdecimal()``, not ``isdigit()``: ``isdigit`` is true of superscripts and
    other "other number" characters, which are not part of a literal — the same
    trap ``validate_name`` avoids for identifiers.
    """
    index = start
    length = len(text)
    if text[index] == "0" and index + 1 < length and text[index + 1] in "xXoObB":
        index += 2
        while index < length and (text[index] in "0123456789abcdefABCDEF_"):
            index += 1
        return index
    while index < length and text[index].isdecimal():
        index += 1
    if index < length and text[index] == ".":
        index += 1
        while index < length and text[index].isdecimal():
            index += 1
    if index < length and text[index] in "eE":
        after = index + 1
        if after < length and text[after] in "+-":
            after += 1
        if after < length and text[after].isdecimal():
            index = after
            while index < length and text[index].isdecimal():
                index += 1
    return index


def _name_kind(name: str, scope: Mapping[str, Any]) -> TokenKind:
    """How ``name`` resolves — the same order the parser resolves it in."""
    if name in scope:
        return TokenKind.VARIABLE
    if name in SYMPY_CONSTANTS:
        return TokenKind.CONSTANT
    if name in sympy_callables():
        return TokenKind.CALLABLE
    return TokenKind.NAME


def _operator_at(text: str, start: int) -> Optional[str]:
    """The operator at ``start``, longest match first, or None."""
    for operator in _OPERATORS:
        if text.startswith(operator, start):
            return operator
    return None


def tokenize(text: str, scope: Optional[Mapping[str, Any]] = None) -> List[Token]:
    """Every run of ``text`` as a :class:`Token`, in order.

    Args:
        text: The expression as the user typed it.
        scope: Name -> value, as ``Calculator.evaluate`` takes it; a name in
            here is a variable rather than a free symbol.

    Returns:
        A list of tokens covering the whole of ``text``, gaps included.
    """
    scope = {} if scope is None else scope
    tokens: List[Token] = []
    index = 0
    length = len(text)

    while index < length:
        char = text[index]

        if char.isspace():
            end = index
            while end < length and text[end].isspace():
                end += 1
            tokens.append(Token(index, end - index, TokenKind.SPACE))
            index = end
        elif char.isdecimal() or (char == "." and index + 1 < length
                                  and text[index + 1].isdecimal()):
            end = _scan_number(text, index)
            tokens.append(Token(index, end - index, TokenKind.NUMBER))
            index = end
        elif _is_name_start(char):
            end = index + 1
            while end < length and _is_name_continue(text[end]):
                end += 1
            tokens.append(Token(index, end - index, _name_kind(text[index:end], scope)))
            index = end
        elif char in _BRACKETS:
            tokens.append(Token(index, 1, TokenKind.BRACKET))
            index += 1
        else:
            operator = _operator_at(text, index)
            if operator is not None:
                tokens.append(Token(index, len(operator), TokenKind.OPERATOR))
                index += len(operator)
            else:
                tokens.append(Token(index, 1, TokenKind.UNKNOWN))
                index += 1

    return tokens
