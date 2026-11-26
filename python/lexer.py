"""Tokenizing the calculator's expression language (pure Python, zero Qt, zero SymPy).

The point of this module is that the *lexical* rules are read by everything that
has to point at a piece of the text: syntax colouring, hover, completion and the
ranges error messages underline. The SymPy name table is static data in
:mod:`python.names`, so importing this module never loads SymPy.

What this is not: a parser, and not a judge. It says what each run of characters
*is*, never whether the expression is valid — that stays with ``Calculator``,
which answers with ``Success`` / ``Failure``. Keeping the verdict there is what
stops a highlighter from claiming ``foo(1)`` is a function call while
``unknown_calls`` reports it as an unknown one (``implicit_multiplication``
turns it into ``f*o**2``).

The one exception is Python's own grammar: two disabled conveniences make text
that is not valid Python at all, and the lexer is where that is already visible.
A standalone ``!`` is only an operator when ``factorial_notation`` is on (``!=``
stays one either way), and with ``implicit_multiplication`` off the operand on
the *right* of a juxtaposition (``2x``, ``2(x)``, ``(x+1)(x-1)``) is
:attr:`Token.invalid` — a spelling for "a ``*`` belongs here". Token kinds and
boundaries still do not otherwise follow the policy: ``x^2``, ``sin x`` and
``split_symbols`` change what the text *means*, not what each run *is*.

The character classes are Python's own (``str.isidentifier``), because the
parser tokenizes with Python's tokenizer: a name this module accepts is a name
SymPy can resolve, and ``x²`` splits into a name and a stray character instead
of looking like one identifier.
"""

from collections.abc import Mapping, Sequence
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, NamedTuple

from .names import SYMPY_CALLABLES, SYMPY_CONSTANTS

if TYPE_CHECKING:
    from .worker_protocol import ParsePolicy


class TokenKind(Enum):
    """What a run of characters is.

    Attributes:
        NUMBER: An integer, float or hex/octal/binary literal.
        NAME: A bare name. Unknown names stay *symbolic* — that is the
            documented permissiveness, not an error.
        VARIABLE: A name that resolves to a stored variable.
        CALLABLE: A name SymPy resolves as a function.
        CONSTANT: A name SymPy resolves as a constant (``pi``, ``E``, ...).
        STRING: A quoted literal. Its contents are data, not source: no name,
            number, operator or bracket inside it is a token of its own.
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
    STRING = auto()
    OPERATOR = auto()
    BRACKET = auto()
    SPACE = auto()
    UNKNOWN = auto()


class Token(NamedTuple):
    """``(start, length, kind)`` — a tuple, so it is also a colour span.

    ``invalid`` marks a spelling the active language cannot mean: the right-hand
    operand of a juxtaposition that only ``implicit_multiplication`` makes legal
    (``2x``, ``(x+1)(x-1)``), or a string its closing quote never reached. The
    kind is kept: a stored variable in ``2x`` is still a ``VARIABLE`` for anything
    that acts on the token (a future quick fix inserts the ``*`` before this
    token), while the renderer paints it as the expression language having no
    use for that spelling.
    """

    start: int
    length: int
    kind: TokenKind
    invalid: bool = False


#: Multi-character first, so ``**`` never lexes as two ``*``. Mirrors what the
#: parser accepts: ``convert_xor`` makes ``^`` a power, ``factorial_notation``
#: makes ``!`` a postfix factorial, and the augmented forms come from
#: ``calculator.AUGMENTED_OPS``.
_OPERATORS: Sequence[str] = (
    "**=", "//=", ">>=", "<<=", "!=", "<=", ">=", "==",
    "**", "//", "<<", ">>",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "+", "-", "*", "/", "%", "^", "!", "=", "<", ">", "~", "&", "|", "@",
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


def _scan_string(text: str, start: int) -> tuple[int, bool]:
    """Index just past the quoted literal at ``start``, and whether it closed.

    Both quote styles and their triple-quoted forms, because the parser hands
    the expression to Python's tokenizer and ``Symbol("x")`` is a supported
    call. Escapes are honoured so ``"a\\"b"`` does not close early; a plain
    string ends at the line break Python would refuse, and an unterminated one
    ends with the text.
    """
    quote = text[start]
    length = len(text)
    if text.startswith(quote * 3, start):
        index = start + 3
        while index < length:
            if text[index] == "\\":
                index += 2
                continue
            if text.startswith(quote * 3, index):
                return index + 3, True
            index += 1
        return length, False

    index = start + 1
    while index < length:
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index + 1, True
        if char == "\n":
            return index, False
        index += 1
    return length, False


def _name_kind(name: str, scope: Mapping[str, Any]) -> TokenKind:
    """How ``name`` resolves — the same order the parser resolves it in."""
    if name in scope:
        return TokenKind.VARIABLE
    if name in SYMPY_CONSTANTS:
        return TokenKind.CONSTANT
    if name in SYMPY_CALLABLES:
        return TokenKind.CALLABLE
    return TokenKind.NAME


def _operator_at(text: str, start: int, factorial: bool = True) -> str | None:
    """The operator at ``start``, longest match first, or None.

    A standalone ``!`` is only an operator when the factorial convenience is
    on; ``!=`` is still matched first and stays one either way.
    """
    for operator in _OPERATORS:
        if operator == "!" and not factorial:
            continue
        if text.startswith(operator, start):
            return operator
    return None


#: Tokens that can stand on the left of a juxtaposition.
_NAME_KINDS = frozenset({
    TokenKind.NAME,
    TokenKind.VARIABLE,
    TokenKind.CALLABLE,
    TokenKind.CONSTANT,
})


def _is_paren(text: str, token: Token) -> bool:
    """Is this token an opening ``(``?

    Only a paren: ``2[0]`` and ``f(x)[0]`` are Python subscripts, which this
    language accepts (the AST gate allows ``Subscript``), so they must not be
    read as a missing ``*``. A ``[`` after a number is not implicit
    multiplication either.
    """
    return token.kind is TokenKind.BRACKET and text[token.start] == "("


def _is_closing_bracket(text: str, token: Token) -> bool:
    return token.kind is TokenKind.BRACKET and text[token.start] in ")]}"


def _is_juxtaposed(text: str, previous: Token, token: Token) -> bool:
    """Is ``token`` the right operand of an implicit multiplication?

    Covers what SymPy's ``implicit_multiplication`` inserts a ``*`` into and
    Python's own grammar rejects: ``2x``, ``2 3``, ``2(x+1)``, ``(a+b)(a-b)``,
    ``f(x)y``. A name followed by ``(`` is a call in Python (``sin(x)``), so it
    is deliberately not one; neither is ``sin x``, which belongs to
    ``implicit_application``.
    """
    if previous.kind is TokenKind.NUMBER:
        return (
            token.kind in _NAME_KINDS
            or token.kind is TokenKind.NUMBER
            or _is_paren(text, token)
        )
    if _is_closing_bracket(text, previous):
        return (
            token.kind in _NAME_KINDS
            or token.kind is TokenKind.NUMBER
            or _is_paren(text, token)
        )
    return False


def tokenize(
    text: str,
    scope: Mapping[str, Any] | None = None,
    policy: "ParsePolicy | None" = None,
) -> list[Token]:
    """Every run of ``text`` as a :class:`Token`, in order.

    Args:
        text: The expression as the user typed it.
        scope: Name -> value, as ``Calculator.evaluate`` takes it; a name in
            here is a variable rather than a free symbol.
        policy: The active parser profile, when the caller has one. Only two
            rules read it (see the module docstring): standalone ``!`` and
            juxtaposition. ``None`` means every convenience is on, which keeps
            the historical colouring for callers that have no settings (tests,
            headless renderers).

    Returns:
        A list of tokens covering the whole of ``text``, gaps included.
    """
    scope = {} if scope is None else scope
    transformations = None if policy is None else policy.transformations
    factorial = transformations is None or "factorial_notation" in transformations
    implicit = (
        transformations is None or "implicit_multiplication" in transformations
    )
    tokens: list[Token] = []
    previous: Token | None = None
    index = 0
    length = len(text)

    while index < length:
        char = text[index]

        if char.isspace():
            end = index
            while end < length and text[end].isspace():
                end += 1
            token = Token(index, end - index, TokenKind.SPACE)
            index = end
        elif char.isdecimal() or (char == "." and index + 1 < length
                                  and text[index + 1].isdecimal()):
            end = _scan_number(text, index)
            token = Token(index, end - index, TokenKind.NUMBER)
            index = end
        elif char in "'\"":
            end, closed = _scan_string(text, index)
            token = Token(index, end - index, TokenKind.STRING, invalid=not closed)
            index = end
        elif _is_name_start(char):
            end = index + 1
            while end < length and _is_name_continue(text[end]):
                end += 1
            token = Token(index, end - index, _name_kind(text[index:end], scope))
            index = end
        elif char in _BRACKETS:
            token = Token(index, 1, TokenKind.BRACKET)
            index += 1
        else:
            operator = _operator_at(text, index, factorial)
            if operator is not None:
                token = Token(index, len(operator), TokenKind.OPERATOR)
                index += len(operator)
            else:
                token = Token(index, 1, TokenKind.UNKNOWN)
                index += 1

        if (
            not implicit
            and previous is not None
            and token.kind is not TokenKind.SPACE
            and _is_juxtaposed(text, previous, token)
        ):
            token = token._replace(invalid=True)
        tokens.append(token)
        if token.kind is not TokenKind.SPACE:
            previous = token

    return tokens
