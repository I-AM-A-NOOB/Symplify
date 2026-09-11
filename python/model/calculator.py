# coding: utf-8
"""Symbolic calculation model built on SymPy.

The one place where user input becomes a value: audit, parse, evaluate. This
module owns the answers to "what does this text mean, which names resolve, and
what counts as a failure" — nothing above it may re-implement that.

Two requests exist: an expression (``evaluate``) and a write to the variable
store (``assign``). Both return ``Success`` or ``Failure``; there is no result
object carrying a half-filled payload behind a boolean.
"""

import difflib
import keyword
import operator
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Mapping, Optional, Union

from sympy import latex
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)

from .variable import is_sympy_name, sympy_callables, validate_name


class ErrorKind(Enum):
    """Why a request could not be answered.

    Attributes:
        SYNTAX: the text is not parseable as an expression.
        UNKNOWN_NAME: a name used as a call that resolves to no function, or an
            augmented assignment to a variable that does not exist.
        INVALID_NAME: an assignment target that is not a legal variable name.
        UNSUPPORTED: a well-formed request this model does not implement.
        INTERNAL: sympy raised something that is not a syntax problem — a bug
            in the request's domain or in this layer, never the user's typo.
    """

    SYNTAX = auto()
    UNKNOWN_NAME = auto()
    INVALID_NAME = auto()
    UNSUPPORTED = auto()
    INTERNAL = auto()


@dataclass(frozen=True)
class Success:
    """A request that produced a value.

    Attributes:
        expression: The request as the user made it (provenance).
        value: The resulting sympy object.
        latex: LaTeX for display; ``''`` when sympy could not render the value.
    """

    expression: str
    value: Any
    latex: str


@dataclass(frozen=True)
class Failure:
    """A request that could not be answered.

    Attributes:
        expression: The request as the user made it.
        kind: Why it failed (see ``ErrorKind``).
        message: What went wrong, safe to show the user.
        hint: Optional "did you mean" style suggestion.
    """

    expression: str
    kind: ErrorKind
    message: str
    hint: str = ""


#: Result of any request: exactly one of the two shapes.
Result = Union[Success, Failure]


@dataclass(frozen=True)
class Assignment:
    """A write to the variable store, as a request rather than a string.

    ``expression`` stays *text* so the expression language (implicit
    multiplication, ``^``, paren-less application) is parsed by exactly one
    parser. Reassembling the write into a new expression string — the previous
    implementation built ``f"{name} {op[0]} ({value})"`` — is what turned
    ``x += 1`` on an undefined ``x`` into the self-referential binding
    ``x = x + 1``.

    Attributes:
        target: Variable name to write.
        op: ``'='`` or an augmented operator (``'+='``, ``'-='``, ``'*='``,
            ``'/='``, ``'%='``).
        expression: The right-hand side, as the user typed it.
    """

    target: str
    op: str = "="
    expression: str = ""


#: Augmented operators mapped to the operation they apply.
AUGMENTED_OPS = {
    "+=": operator.add,
    "-=": operator.sub,
    "*=": operator.mul,
    "/=": operator.truediv,
    "%=": operator.mod,
}

ASSIGN_OPS = frozenset({"="}) | frozenset(AUGMENTED_OPS)

#: ``name(`` — a call, as opposed to juxtaposition like ``2(x + 1)``.
_CALL_RE = re.compile(r"(?<![\w.])([^\W\d]\w*)\s*\(")


def render_latex(value: Any) -> str:
    """LaTeX for ``value``, or ``''`` when sympy cannot render it.

    Deliberately outside the evaluation path: a rendering problem must never be
    reported as a calculation failure.
    """
    try:
        return latex(value)
    except Exception:
        return ""


class Calculator:
    """Symbolic calculator model.

    Provides the two requests the UI can make — evaluate an expression, assign
    to a variable — and the name audit that keeps both honest.
    """

    def __init__(self):
        """Initialize the parse transformations shared by every request."""
        self.transformations = standard_transformations + (
            implicit_multiplication,
            convert_xor,
        )

    def evaluate(
        self, expression: str, scope: Optional[Mapping[str, Any]] = None
    ) -> Result:
        """Evaluate ``expression`` with ``scope`` as the visible variables.

        Args:
            expression: The text to evaluate.
            scope: Visible variable values (``VariableManager.list_all()``).

        Returns:
            Success with the sympy value, or Failure describing the problem.
        """
        variables = dict(scope) if scope else {}
        unknown = self.unknown_calls(expression, variables)
        if unknown:
            return Failure(
                expression,
                ErrorKind.UNKNOWN_NAME,
                f"unknown function '{unknown[0]}'",
                self._suggest(unknown[0]),
            )
        return self._parse(expression, variables)

    def assign(
        self, assignment: Assignment, scope: Optional[Mapping[str, Any]] = None
    ) -> Result:
        """Answer an ``Assignment``: validate the target, then evaluate.

        The target is checked *before* anything is evaluated, so a rejected
        write cannot leave a history entry, a log line or a variable behind.

        Args:
            assignment: The write request.
            scope: Visible variable values.

        Returns:
            Success carrying the value that should be stored, or Failure.
        """
        variables = dict(scope) if scope else {}
        target = assignment.target.strip()
        op = assignment.op
        request = f"{target} {op} {assignment.expression}".strip()

        if not validate_name(target):
            return Failure(
                request,
                ErrorKind.INVALID_NAME,
                f"invalid variable name: '{target}'",
                "names start with a letter or underscore and hold only letters, "
                "digits and underscores",
            )
        if op not in ASSIGN_OPS:
            return Failure(
                request,
                ErrorKind.UNSUPPORTED,
                f"unsupported operator: '{op}'",
                "use one of " + ", ".join(sorted(ASSIGN_OPS)),
            )
        if op != "=" and target not in variables:
            return Failure(
                request,
                ErrorKind.UNKNOWN_NAME,
                f"'{target}' is not defined",
                f"'{op}' needs an existing variable; define it with '=' first",
            )

        parsed = self.evaluate(assignment.expression, variables)
        if isinstance(parsed, Failure):
            return Failure(request, parsed.kind, parsed.message, parsed.hint)

        if op == "=":
            value = parsed.value
        else:
            value = AUGMENTED_OPS[op](variables[target], parsed.value)
        return Success(request, value, render_latex(value))

    def unknown_calls(self, expression: str, scope: Mapping[str, Any]) -> List[str]:
        """Names used as calls that resolve to no function, in order of use.

        ``implicit_multiplication`` silently rewrites an unknown call into a
        product (``bar(2)`` becomes ``2*bar``), which changes what the user
        wrote instead of reporting it. Names declared in ``scope`` are left
        alone: those resolve to a value, and juxtaposition with a value is the
        documented meaning of ``f(x)`` there.
        """
        found: List[str] = []
        for name in _CALL_RE.findall(expression):
            if name in scope or is_sympy_name(name) or keyword.iskeyword(name):
                continue
            if name not in found:
                found.append(name)
        return found

    def _parse(self, expression: str, scope: Mapping[str, Any]) -> Result:
        """Parse ``expression`` (sympy auto-evaluates as it constructs)."""
        text = expression.strip()
        if not text:
            return Failure(expression, ErrorKind.SYNTAX, "nothing to evaluate")
        try:
            value = parse_expr(
                text, transformations=self.transformations, local_dict=dict(scope)
            )
        except SyntaxError as exc:
            return Failure(expression, ErrorKind.SYNTAX, str(exc))
        except Exception as exc:
            return Failure(
                expression, ErrorKind.INTERNAL, f"{type(exc).__name__}: {exc}"
            )
        return Success(expression, value, render_latex(value))

    def _suggest(self, name: str) -> str:
        """A 'did you mean' hint for an unresolvable call name."""
        matches = difflib.get_close_matches(name, sympy_callables(), n=1, cutoff=0.7)
        if matches:
            return f"did you mean '{matches[0]}'?"
        return "if you meant multiplication, write the factors explicitly"
