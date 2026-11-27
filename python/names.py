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

#: The names a plot may leave free. The app no longer seeds them into the Store;
#: they are ordinary free symbols, and only the legacy/headless path pre-fills a
#: table with them. Kept here (zero SymPy) so the plot rule and the warning cannot
#: drift.
PLOTTING_NAMES = ("x", "y")

__all__ = [
    "PLOTTING_NAMES",
    "SYMPY_CALLABLES",
    "SYMPY_CONSTANTS",
    "SYMPY_VERSION",
    "is_sympy_name",
    "reserved_name_kind",
    "validate_name",
]


def is_sympy_name(name: str) -> bool:
    """True when ``name`` is a SymPy constant or callable (static table)."""
    return name in SYMPY_CONSTANTS or name in SYMPY_CALLABLES


def reserved_name_kind(name: str) -> str | None:
    """Why ``name`` changes what input means: ``"builtin"``, ``"plotting"`` or None.

    The warning is a pure function of the name and this static table, so the UI
    derives it here instead of trusting a display sentence the Compute worker
    persisted. That keeps a changed source string from orphaning old entries and
    avoids importing :mod:`python.model` (and SymPy) into the UI for a warning.
    """
    if is_sympy_name(name):
        return "builtin"
    if name in PLOTTING_NAMES:
        return "plotting"
    return None


def validate_name(name: object) -> bool:
    """True when ``name`` is a legal variable name."""
    return isinstance(name, str) and name.isidentifier() and not keyword.iskeyword(name)
