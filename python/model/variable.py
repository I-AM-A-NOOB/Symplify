# coding: utf-8
"""Variable management model for the calculator.

Provides CRUD operations with name validation. Independent of any UI.
Variables are snapshot entries: the sympy object plus its display string
and a coarse type label. There is no dependency tracking -- an assignment
stores exactly what it evaluated to at assignment time; expressions that
reference yet-unassigned variables simply stay symbolic (native sympy
behavior), and invalid input is kept as an invalid (NaN) entry.
"""

import keyword
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional

#: Names sympy already defines, which a variable would shadow. User input is
#: resolved against sympy's namespace, so these are exactly the names that can
#: silently change what an expression means.
SYMPY_CONSTANTS = frozenset({
    "pi",
    "E",
    "I",
    "oo",
    "zoo",
    "nan",
    "GoldenRatio",
    "EulerGamma",
    "Catalan",
})


@lru_cache(maxsize=1)
def sympy_callables() -> frozenset:
    """Public callable names in sympy's namespace (cached; built on first use)."""
    import sympy as sp

    return frozenset(
        name for name in dir(sp)
        if not name.startswith("_") and callable(getattr(sp, name, None))
    )


def is_sympy_name(name: str) -> bool:
    """True when ``name`` is a sympy constant or callable the parser resolves."""
    return name in SYMPY_CONSTANTS or name in sympy_callables()


def validate_name(name: str) -> bool:
    """Check if a variable name is legal (the single source of truth).

    Identifier rules: first char alpha/underscore, then alnum/underscore, and
    not a Python keyword. Both the variable store and the assignment path use
    this function, so UI and model can never disagree.

    Returns:
        True if the name is valid, False otherwise.
    """
    if not name or not isinstance(name, str):
        return False

    if not (name[0].isalpha() or name[0] == "_"):
        return False

    if not all(c.isalnum() or c == "_" for c in name[1:]):
        return False

    return not keyword.iskeyword(name)


def classify_type(value: Any) -> str:
    """Classify a sympy object into a coarse, human-readable type label.

    Semantic categories are used wherever a predicate covers a whole
    family; anything unmatched falls back to the raw sympy class name so
    every possible value still gets a label.
    """
    import sympy as sp

    if value is None:
        return "Invalid"
    if isinstance(value, sp.MatrixBase):
        return "Matrix"
    if value is sp.nan:
        return "NaN"
    if value in (sp.oo, -sp.oo, sp.zoo):
        return "Infinity"
    if isinstance(value, sp.logic.boolalg.BooleanAtom):
        return "Boolean"
    if isinstance(value, sp.core.relational.Relational):
        return "Equation"
    if isinstance(value, sp.Symbol):
        return "Symbol"
    if isinstance(value, sp.Integer):
        return "Integer"
    if isinstance(value, sp.Rational):
        return "Rational"
    if isinstance(value, sp.Float):
        return "Float"
    if getattr(value, "is_number", False):
        return "Number"
    if isinstance(value, sp.core.numbers.NumberSymbol):
        return "Constant"
    if isinstance(value, sp.Function):
        return "Function"
    if isinstance(value, sp.Expr):
        return "Expression"
    return type(value).__name__


@dataclass
class VariableEntry:
    """A stored variable: sympy value plus its display metadata.

    Attributes:
        name: Variable name.
        obj: The sympy object; None when the entry is invalid.
        expr_str: Display expression -- canonical str(obj) for valid
            entries, the raw user input for invalid ones.
        type_label: Coarse type classification (see ``classify_type``).
        valid: False when the entry comes from an invalid assignment;
            its value is then NaN.
    """

    name: str
    obj: Optional[Any]
    expr_str: str
    type_label: str
    valid: bool


class VariableManager:
    """Manages calculator variables."""

    def __init__(self):
        """Initialize the variable manager."""
        self._variables: Dict[str, VariableEntry] = {}

    def validate_name(self, name: str) -> bool:
        """Check whether ``name`` is legal (delegates to the module function)."""
        return validate_name(name)

    @staticmethod
    def is_sympy_builtin(name: str) -> bool:
        """Check whether ``name`` shadows a sympy constant or function.

        Returns:
            True when sympy already defines the name. Assigning it is still
            allowed, but every expression using that name changes meaning.
        """
        return is_sympy_name(name)

    def entry(self, name: str) -> Optional[VariableEntry]:
        """Get the full entry for ``name``, or None if not found."""
        return self._variables.get(name)

    def names(self) -> List[str]:
        """Get variable names in insertion order."""
        return list(self._variables.keys())

    def entries(self) -> List[VariableEntry]:
        """Get all entries in insertion order."""
        return list(self._variables.values())

    def get(self, name: str) -> Any:
        """Get a variable's sympy value, or None if not found/invalid."""
        entry = self._variables.get(name)
        return entry.obj if entry and entry.valid else None

    def save(self, name: str, value: Any) -> None:
        """Store a valid variable snapshot (a sympy object).

        Raises:
            ValueError: If the variable name is invalid.
        """
        if not self.validate_name(name):
            raise ValueError(f"Invalid variable name: '{name}'")
        self._variables[name] = VariableEntry(
            name=name,
            obj=value,
            expr_str=str(value),
            type_label=classify_type(value),
            valid=True,
        )

    def save_invalid(self, name: str, raw_expr: str) -> None:
        """Store an invalid assignment: keep the raw input, value is NaN.

        Raises:
            ValueError: If the variable name is invalid.
        """
        if not self.validate_name(name):
            raise ValueError(f"Invalid variable name: '{name}'")
        self._variables[name] = VariableEntry(
            name=name,
            obj=None,
            expr_str=raw_expr,
            type_label="Invalid",
            valid=False,
        )

    def delete(self, name: str) -> bool:
        """Delete a variable.

        Returns:
            True if deleted, False if not found.
        """
        if name in self._variables:
            del self._variables[name]
            return True
        return False

    def exists(self, name: str) -> bool:
        """Check if a variable exists."""
        return name in self._variables

    def list_all(self) -> Dict[str, Any]:
        """Get the valid variables as a dictionary (for evaluation)."""
        return {n: e.obj for n, e in self._variables.items() if e.valid}

    def rename(self, old_name: str, new_name: str) -> bool:
        """Rename a variable.

        Raises:
            ValueError: If the new name is invalid or already exists.
        """
        if old_name not in self._variables:
            return False

        if not self.validate_name(new_name):
            raise ValueError(f"Invalid variable name: '{new_name}'")

        if new_name in self._variables and new_name != old_name:
            raise ValueError(f"Variable '{new_name}' already exists")

        entry = self._variables[old_name]
        entry.name = new_name
        # Rebuild in order so a rename keeps the entry's position: the table
        # renames its row without reordering it, and the two orders must not
        # disagree.
        self._variables = {
            (new_name if key == old_name else key): value
            for key, value in self._variables.items()
        }
        return True

    def clear(self) -> None:
        """Clear all variables."""
        self._variables.clear()

    def generate_unique_name(self, base: str = "var") -> str:
        """Generate a unique variable name based on ``base``."""
        counter = 1
        while True:
            name = f"{base}_{counter}"
            if name not in self._variables and self.validate_name(name):
                return name
            counter += 1
