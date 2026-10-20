# coding: utf-8
"""Symbolic calculation model built on SymPy.

The one place where user input becomes a value: audit, parse, evaluate. This
module owns the answers to "what does this text mean, which names resolve, and
what counts as a failure" — nothing above it may re-implement that.

Two requests exist: an expression (``evaluate``) and a write to the variable
store (``assign``). Both return ``Success`` or ``Failure``; there is no result
object carrying a half-filled payload behind a boolean.

**A result is simplified before it is answered.** The parser returns whatever
sympy's constructors leave behind, which is not always the simplest form the
user asked for — ``sin(x)**2 + cos(x)**2`` stayed as typed, ``1/x + 1/y`` stayed
two fractions. Every value is therefore run through ``sympy.simplify`` (see
``_simplified``), *after* the transform call has been identified, so a
derivative still knows the function it came from.
"""

import difflib
import keyword
import operator
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Mapping, Optional, Union

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)
from .latex import render_latex, render_latex_definition
from .plotting import Origin
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
        TIMEOUT: the request exceeded the backend's deadline and was cancelled;
            raised by the frontend/backend boundary, never by the model itself.
    """

    SYNTAX = auto()
    UNKNOWN_NAME = auto()
    INVALID_NAME = auto()
    UNSUPPORTED = auto()
    INTERNAL = auto()
    TIMEOUT = auto()


@dataclass(frozen=True)
class Success:
    """A request that produced a value.

    Attributes:
        expression: The request as the user made it (provenance).
        value: The resulting sympy object.
        latex: LaTeX for display; ``''`` when sympy could not render the value.
        origin: The transform call the request *was* (``diff``, ``solve``, …),
            when the request was exactly that call — see
            ``python/model/plotting.py``. ``None`` for everything else, and for
            assignments: a write defines one value, so it has nothing to explain.
    """

    expression: str
    value: Any
    latex: str
    origin: Optional[Origin] = None


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

#: Calls whose result is a different function of x, so a plot can show what it
#: was derived from (see ``python/model/plotting.py``).
_TRANSFORM_CALLS = (
    "diff", "Derivative", "integrate", "Integral",
    "solve", "solveset", "roots", "linsolve", "nonlinsolve", "nsolve",
)


def _simplified(value: Any) -> Any:
    """``value`` through sympy's ``simplify``, where that means something.

    Results that are not one sympy object are left alone: ``solve`` answers with
    a list of roots, and ``simplify`` raises on a list (its input is expected to
    be a Basic). The roots it returns are in their simplest form already.

    A failure is not a calculation failure: ``simplify`` throwing on some
    exotic object would only mean "no simplification", so the raw value is
    answered instead — the request itself succeeded.
    """
    if isinstance(value, (list, tuple, set, dict)):
        return value
    try:
        return sympy.simplify(value)
    except Exception:  # noqa: BLE001 - no simplification is not a failed request
        return value


class _TransformRecorder:
    """Notes the transforming calls one parse makes, without parsing anything.

    The parser is the only thing that understands the input language (implicit
    multiplication, ``^``, paren-less application), so instead of looking for
    ``diff(`` in the text, sympy's own callables are shadowed in the evaluation
    namespace and each call is noted while it runs. A call only counts when its
    *result is the value the request produced* (identity, see :meth:`top_level`):
    in ``diff(f, x) + 1`` the derivative is a subexpression the user then
    changed, so it is not what a plot should explain.

    Names already in the scope win over the wrappers, so a user variable called
    ``diff`` keeps meaning what it meant before. The wrappers call exactly the
    sympy function they shadow and return its result unchanged.
    """

    def __init__(self) -> None:
        """Start an empty record for one evaluation."""
        self._calls: List[tuple] = []

    def namespace(self, scope: Mapping[str, Any]) -> dict:
        """``scope`` plus a recording wrapper for every transform not in it."""
        namespace = dict(scope)
        for name in _TRANSFORM_CALLS:
            function = getattr(sympy, name, None)
            if callable(function):
                namespace.setdefault(name, self._wrapper(name, function))
        return namespace

    def _wrapper(self, name: str, function: Any) -> Any:
        """``function``, recording ``(Origin, result)`` each time it is called."""
        def call(*args: Any, **kwargs: Any) -> Any:
            result = function(*args, **kwargs)
            self._calls.append((Origin(name, args[0] if args else None), result))
            return result

        return call

    def top_level(self, value: Any) -> Optional[Origin]:
        """The call the request *was*, or None when it was not one.

        Identity, not equality: ``parse_expr`` returns the call's own object for
        a bare call, and a new object as soon as anything is wrapped around it.
        """
        for origin, result in reversed(self._calls):
            if result is value:
                return origin
        return None


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
        # The definition, not just the value: the calculator's result pane and the
        # history card both show this LaTeX on its own, and a bare number beside the
        # name they already print reads as two answers to the same question. The
        # operator is not repeated — `x += 1` is reported as the `x = …` it made.
        return Success(request, value, render_latex_definition(target, value))

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
        recorder = _TransformRecorder()
        try:
            value = parse_expr(
                text,
                transformations=self.transformations,
                local_dict=recorder.namespace(scope),
            )
        except SyntaxError as exc:
            return Failure(expression, ErrorKind.SYNTAX, str(exc))
        except Exception as exc:
            return Failure(
                expression, ErrorKind.INTERNAL, f"{type(exc).__name__}: {exc}"
            )
        # The origin is decided on the parser's own object: `simplify` returns a
        # *new* expression, and identity is what makes a call top-level.
        origin = recorder.top_level(value)
        value = _simplified(value)
        return Success(expression, value, render_latex(value), origin)

    def _suggest(self, name: str) -> str:
        """A 'did you mean' hint for an unresolvable call name."""
        matches = difflib.get_close_matches(name, sympy_callables(), n=1, cutoff=0.7)
        if matches:
            return f"did you mean '{matches[0]}'?"
        return "if you meant multiplication, write the factors explicitly"
