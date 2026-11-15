"""Restore a SymPy object from the ``srepr`` the Compute worker produced.

``srepr`` is the only recoverable form the Store keeps. It is always produced by
the Compute worker — never by the UI — but this module still treats it as an
untrusted string: the text is parsed as Python, every node is checked against a
small grammar, and the result is evaluated with no builtins and only SymPy's
Basic constructors/singletons in scope. There is no attribute access, subscript,
import, lambda, or arbitrary call.

This is the one place the Compute worker evaluates text, and it is deliberately
separate from the calculator's expression parser: the user's input is parsed as
mathematics, while ``srepr`` is SymPy's own constructor spelling.
"""

from __future__ import annotations

import ast
from functools import lru_cache
from typing import Any

import sympy

#: A guard against a pathologically large snapshot entry. A real expression's
#: srepr is far below this; the cap keeps parse/eval cost bounded.
MAX_SREPR_CHARS = 1_000_000


class SreprError(ValueError):
    """An ``srepr`` string is malformed, unsupported, or unsafe to evaluate."""


@lru_cache(maxsize=1)
def _namespace() -> dict[str, Any]:
    """The names ``srepr`` may mention: SymPy classes and singletons.

    Mutable matrices are ``MatrixBase`` rather than ``Basic``; ``srepr`` emits
    ``MutableDenseMatrix(...)`` for them, so they are admitted explicitly. The
    namespace contains values, never functions from the wider Python runtime.
    """
    namespace: dict[str, Any] = {}
    for name, value in vars(sympy).items():
        if not name.isidentifier():
            continue
        if isinstance(value, type):
            if issubclass(value, sympy.Basic) or issubclass(value, sympy.MatrixBase):
                namespace[name] = value
        elif isinstance(value, sympy.Basic):
            namespace[name] = value
    return namespace


def _is_allowed_callee(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in _namespace()
    # ``srepr(Function('f')(x))`` is ``Function('f')(Symbol('x'))``: the one
    # call-of-a-call SymPy emits, and only from its function factory.
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"Function", "WildFunction"}
    )


def _validate(node: ast.AST) -> None:
    """Reject every node that is not a constructor call over literal data."""
    if isinstance(node, ast.Call):
        if not _is_allowed_callee(node.func):
            raise SreprError("only SymPy constructors may be called")
        if isinstance(node.func, ast.Call):
            _validate(node.func)
        for argument in node.args:
            _validate(argument)
        for keyword in node.keywords:
            if keyword.arg is None:
                raise SreprError("starred keywords are not allowed")
            _validate(keyword.value)
        return
    if isinstance(node, ast.Name):
        if node.id not in _namespace():
            raise SreprError(f"unknown name {node.id!r}")
        return
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (str, int, float, complex, bool, type(None))):
            raise SreprError(f"unsupported constant {node.value!r}")
        return
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for element in node.elts:
            _validate(element)
        return
    if isinstance(node, ast.Dict):
        for key in node.keys:
            if key is None:
                raise SreprError("dictionary unpacking is not allowed")
            _validate(key)
        for value in node.values:
            _validate(value)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        # ``srepr(-oo)`` is the one unary spelling SymPy emits; numbers are
        # already ``Integer(-1)``/``Float('-1.5')`` at this layer.
        if isinstance(node.operand, ast.Name) and node.operand.id == "oo":
            return
        if isinstance(node.operand, ast.Constant) and isinstance(
            node.operand.value, (int, float)
        ):
            return
        raise SreprError("unary minus is only allowed on a constant")
    raise SreprError(f"{type(node).__name__} is not allowed in srepr")


def restore_srepr(text: str) -> Any:
    """The SymPy object spelled by ``text``, or raise :class:`SreprError`.

    The returned object is a SymPy ``Basic`` or a matrix; a name that resolves
    to a class rather than an instance is rejected.
    """
    if not isinstance(text, str) or not text:
        raise SreprError("srepr must be a non-empty string")
    if len(text) > MAX_SREPR_CHARS:
        raise SreprError(f"srepr is longer than {MAX_SREPR_CHARS} characters")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise SreprError(f"not a valid srepr: {exc}") from None
    _validate(tree.body)
    try:
        value = eval(
            compile(tree, "<srepr>", "eval"),
            {"__builtins__": {}},
            _namespace(),
        )
    except Exception as exc:  # noqa: BLE001 - report as one restore failure
        raise SreprError(f"could not restore srepr: {exc}") from None
    if not isinstance(value, (sympy.Basic, sympy.MatrixBase)):
        raise SreprError(f"srepr produced {type(value).__name__}, not a SymPy object")
    return value
