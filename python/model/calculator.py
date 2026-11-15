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

import ast
import difflib
import keyword
import operator
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication,
    null,
    standard_transformations,
    stringify_expr,
)

from ..worker_protocol import Assignment, ErrorKind
from .latex import render_latex, render_latex_definition
from .plotting import Origin
from .variable import is_sympy_name, sympy_callables, validate_name

#: SymPy callables that parse/compile/print/evaluate strings or shells. They are
#: removed from the parser's globals and rejected at the AST gate as well: the
#: calculator's input is untrusted, and ``parse_expr`` itself is an ``eval``.
_UNSAFE_CALLS = frozenset({
    "S", "sympify", "parse_expr", "evaluate", "lambdify", "codegen",
    "autowrap", "ufuncify", "llvm_callable", "import_module", "preview",
    "init_printing", "init_session", "plot", "plot_implicit", "plot_parametric",
    "plot3d", "pprint", "pretty_print", "print_tree", "pager_print", "textplot",
})

#: Constructors whose string argument is data, not source. ``Symbol``/``Function``
#: carry names; ``symbols`` splits a whitespace/comma list of them; ``Float``
#: carries the numeric literal the tokenizer produced.
_STRING_CALLS = frozenset({
    "Symbol", "Dummy", "Wild", "Function", "Float", "symbols",
})

#: SymPy methods an expression may call. Attribute *access* stays forbidden:
#: a bare attribute can walk into a class, so only these calls are admitted.
#: The list is the expression language's surface, not a security denylist; a
#: method joins it with a test that shows the value it returns.
_SAFE_METHODS = frozenset({
    "subs", "xreplace", "replace", "match", "has", "atoms",
    "diff", "integrate", "limit", "series", "sum", "product", "doit",
    "simplify", "expand", "factor", "cancel", "together", "apart",
    "collect", "coeff", "as_numer_denom", "as_real_imag", "as_independent",
    "as_coefficients_dict", "as_ordered_factors", "as_ordered_terms",
    "compute_leading_term", "equals", "evalf", "n", "rewrite",
    "inverse", "inv", "det", "trace", "transpose", "adjugate", "cofactor",
    "minor", "submatrix", "extract", "reshape", "row", "col", "tolist",
    "cross", "dot", "norm", "eigenvals", "eigenvects", "diagonalize",
    "charpoly", "minpoly", "nullspace", "columnspace", "rowspace", "rref",
    "lu", "cholesky", "solve", "inv_mod",
})

#: Read-only SymPy properties an expression may read. Unlike methods, these are
#: plain attribute reads; they are limited to values (tuples, numbers, sets,
#: booleans) and never expose a class or a function's globals.
_SAFE_PROPERTIES = frozenset({
    "free_symbols", "args", "shape", "rows", "cols", "T", "H",
    "is_number", "is_real", "is_integer", "is_rational", "is_positive",
    "is_negative", "is_zero", "is_prime", "is_finite", "is_infinite",
    "is_commutative",
})

_SAFE_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_SAFE_UNARYOPS = (ast.UAdd, ast.USub)
_SAFE_COMPARES = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_FLOAT_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
#: ``symbols("x y")`` reads identifiers, not code. Separators/order marks are
#: enough; quotes, parentheses, operators and backslashes stay out.
_SYMBOLS_RE = re.compile(r"[\w\s,:]+")


class _UnsafeExpression(ValueError):
    """The transformed expression is outside the calculator's safe grammar."""


@lru_cache(maxsize=1)
def _parser_globals() -> dict:
    """A SymPy namespace with no Python builtins and no eval/compile helpers."""
    namespace: dict = {}
    exec("from sympy import *", namespace)
    namespace.pop("__builtins__", None)
    for name in tuple(namespace):
        if (name in _UNSAFE_CALLS
                or name.startswith("print_")
                or name.startswith("pprint_")):
            namespace.pop(name, None)
    # The transformations use these names for ``max(a, b)``/``min(a, b)``.
    namespace["max"] = sympy.Max
    namespace["min"] = sympy.Min
    # Explicit, so eval cannot inject the real builtins behind our back.
    namespace["__builtins__"] = {}
    return namespace


def _validate_safe_ast(node: ast.AST, allowed_names: set[str]) -> None:
    """Reject everything except arithmetic, SymPy calls/methods and data.

    The input goes through SymPy's tokenizer, so the generated code is Python.
    Attribute access, lambdas, comprehensions, imports and arbitrary calls are
    the escape routes from that code; none of them is part of the calculator's
    expression language. A method call is admitted only when its name is in
    :data:`_SAFE_METHODS`; a bare attribute (``x.__class__``) is not.
    """
    if isinstance(node, ast.Expression):
        _validate_safe_ast(node.body, allowed_names)
    elif isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, str) or isinstance(value, bytes) or value is None \
                or value is Ellipsis:
            raise _UnsafeExpression("string constants are not supported")
    elif isinstance(node, ast.Name):
        if not isinstance(node.ctx, ast.Load):
            raise _UnsafeExpression("assignment is not allowed in an expression")
        if node.id.startswith("__") or node.id not in allowed_names:
            raise _UnsafeExpression(f"unknown name '{node.id}'")
    elif isinstance(node, ast.BinOp):
        if not isinstance(node.op, _SAFE_BINOPS):
            raise _UnsafeExpression("operator is not supported")
        _validate_safe_ast(node.left, allowed_names)
        _validate_safe_ast(node.right, allowed_names)
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _SAFE_UNARYOPS):
            raise _UnsafeExpression("operator is not supported")
        _validate_safe_ast(node.operand, allowed_names)
    elif isinstance(node, ast.Compare):
        if not all(isinstance(op, _SAFE_COMPARES) for op in node.ops):
            raise _UnsafeExpression("comparison is not supported")
        _validate_safe_ast(node.left, allowed_names)
        for comparator in node.comparators:
            _validate_safe_ast(comparator, allowed_names)
    elif isinstance(node, ast.Call):
        allow_strings = False
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name.startswith("__") or name in _UNSAFE_CALLS or name not in allowed_names:
                raise _UnsafeExpression(f"function '{name}' is not allowed")
            allow_strings = name in _STRING_CALLS
        elif isinstance(node.func, ast.Attribute):
            # A method call, never a bare attribute read: the base is an
            # expression this gate already accepts, the name is whitelisted and
            # no dunder can reach a class or a function's globals.
            name = node.func.attr
            if "__" in name or name not in _SAFE_METHODS:
                raise _UnsafeExpression(f"method '{name}' is not allowed")
            _validate_safe_ast(node.func.value, allowed_names)
        else:
            raise _UnsafeExpression("only named functions and SymPy methods can be called")
        for argument in node.args:
            if allow_strings and isinstance(argument, ast.Constant) \
                    and isinstance(argument.value, str):
                if name == "Float" and not _FLOAT_RE.fullmatch(argument.value):
                    raise _UnsafeExpression("invalid numeric literal")
                if name == "symbols" and not _SYMBOLS_RE.fullmatch(argument.value):
                    raise _UnsafeExpression("symbols() takes a name list, not code")
                continue
            _validate_safe_ast(argument, allowed_names)
        for keyword_arg in node.keywords:
            if keyword_arg.arg is None:
                raise _UnsafeExpression("keyword expansion is not supported")
            if allow_strings and isinstance(keyword_arg.value, ast.Constant) \
                    and isinstance(keyword_arg.value.value, str):
                if name == "Float" and not _FLOAT_RE.fullmatch(keyword_arg.value.value):
                    raise _UnsafeExpression("invalid numeric literal")
                if name == "symbols" and not _SYMBOLS_RE.fullmatch(keyword_arg.value.value):
                    raise _UnsafeExpression("symbols() takes a name list, not code")
                continue
            _validate_safe_ast(keyword_arg.value, allowed_names)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for element in node.elts:
            _validate_safe_ast(element, allowed_names)
    elif isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if key is None:
                raise _UnsafeExpression("keyword expansion is not supported")
            _validate_safe_ast(key, allowed_names)
            _validate_safe_ast(value, allowed_names)
    elif isinstance(node, ast.Subscript):
        _validate_safe_ast(node.value, allowed_names)
        _validate_safe_ast(node.slice, allowed_names)
    elif isinstance(node, ast.Slice):
        for part in (node.lower, node.upper, node.step):
            if part is not None:
                _validate_safe_ast(part, allowed_names)
    elif isinstance(node, ast.Attribute):
        if "__" in node.attr or node.attr not in _SAFE_PROPERTIES:
            raise _UnsafeExpression("attribute access is only allowed for a SymPy method call")
        _validate_safe_ast(node.value, allowed_names)
    else:
        raise _UnsafeExpression(f"{type(node).__name__} is not supported")


def _safe_parse_expr(text: str, local_dict: dict, transformations: tuple) -> Any:
    """`parse_expr`'s transform/eval pipeline, gated to a safe AST."""
    globals_dict = _parser_globals()
    try:
        code = stringify_expr(text, local_dict, globals_dict, transformations)
        tree = ast.parse(code, mode="eval")
        _validate_safe_ast(tree, set(globals_dict) | set(local_dict))
        return eval(compile(tree, "<symplify>", "eval"), globals_dict, local_dict)
    finally:
        for name in local_dict.pop(null, ()):
            local_dict[name] = null


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
        plot: Plain plot specs (``{"program", "label", "role"}``) built by the
            worker; qmlmathplot consumes the programs directly. Empty for the
            pure model and for results with nothing to draw.
    """

    expression: str
    value: Any
    latex: str
    origin: Origin | None = None
    plot: tuple = ()


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
Result = Success | Failure


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
        self._calls: list[tuple] = []

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

    def top_level(self, value: Any) -> Origin | None:
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
        self, expression: str, scope: Mapping[str, Any] | None = None
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
        self, assignment: Assignment, scope: Mapping[str, Any] | None = None
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
        latex = render_latex_definition(target, value)
        return Success(request, value, latex)

    def unknown_calls(self, expression: str, scope: Mapping[str, Any]) -> list[str]:
        """Names used as calls that resolve to no function, in order of use.

        ``implicit_multiplication`` silently rewrites an unknown call into a
        product (``bar(2)`` becomes ``2*bar``), which changes what the user
        wrote instead of reporting it. Names declared in ``scope`` are left
        alone: those resolve to a value, and juxtaposition with a value is the
        documented meaning of ``f(x)`` there.
        """
        found: list[str] = []
        for name in _CALL_RE.findall(expression):
            if name in scope or is_sympy_name(name) or keyword.iskeyword(name):
                continue
            if name not in found:
                found.append(name)
        return found

    def _parse(self, expression: str, scope: Mapping[str, Any]) -> Result:
        """Parse through SymPy's tokenizer, then a safe-AST eval boundary.

        ``parse_expr`` itself is ``eval`` on generated code; see
        `_safe_parse_expr`. SymPy auto-evaluates as it constructs the value.
        """
        text = expression.strip()
        if not text:
            return Failure(expression, ErrorKind.SYNTAX, "nothing to evaluate")
        recorder = _TransformRecorder()
        try:
            value = _safe_parse_expr(
                text, recorder.namespace(scope), self.transformations
            )
        except _UnsafeExpression as exc:
            return Failure(expression, ErrorKind.SYNTAX, str(exc))
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
