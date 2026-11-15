"""The variable-name grammar, with no Qt and no SymPy.

The Store worker validates names but must not import :mod:`python.model` (that
package loads SymPy). Keeping the one rule here lets the model, the workers and
the future Store share exactly the same answer.

A name must be a valid Python identifier and not a keyword. Delegating to
``str.isidentifier`` (rather than hand-rolled ``isalpha``/``isalnum`` checks)
keeps the rule in lockstep with SymPy's parser, which tokenizes with the same
grammar: e.g. ``x²`` (a superscript two) is ``isalnum`` but not a valid
identifier, so an ad-hoc check would admit a name that could never be referenced
back in an expression.
"""

import json
import keyword
from pathlib import Path

#: SymPy names the UI lexer may colour. Generated from the installed SymPy by
#: ``scripts/update_sympy_names.py``; never import SymPy just to read it.
_NAMES = json.loads(
    Path(__file__).with_name("sympy_names.json").read_text(encoding="utf-8")
)
SYMPY_CONSTANTS = frozenset(_NAMES["constants"])
SYMPY_CALLABLES = frozenset(_NAMES["callables"])
SYMPY_VERSION = str(_NAMES.get("sympy_version", ""))

__all__ = [
    "SYMPY_CALLABLES",
    "SYMPY_CONSTANTS",
    "SYMPY_VERSION",
    "is_sympy_name",
    "validate_name",
]


def is_sympy_name(name: str) -> bool:
    """True when ``name`` is a SymPy constant or callable (static table)."""
    return name in SYMPY_CONSTANTS or name in SYMPY_CALLABLES


def validate_name(name: object) -> bool:
    """True when ``name`` is a legal variable name."""
    return isinstance(name, str) and name.isidentifier() and not keyword.iskeyword(name)
