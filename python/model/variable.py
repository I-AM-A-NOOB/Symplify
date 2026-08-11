# coding: utf-8
"""Variable management model for the calculator.

Provides CRUD operations with name validation. Independent of any UI.
The legacy observer pattern of the widgets app is not carried over;
ViewModels notify the view layer directly.
"""

import keyword
from typing import Any, Dict


class VariableManager:
    """Manages calculator variables."""

    def __init__(self):
        """Initialize the variable manager."""
        self._variables: Dict[str, Any] = {}
        self._revision: int = 0

    @property
    def revision(self) -> int:
        """Monotonic counter bumped on every mutation (for cache invalidation)."""
        return self._revision

    def _touch(self) -> None:
        """Mark the manager as changed."""
        self._revision += 1

    def validate_name(self, name: str) -> bool:
        """Check if a variable name is legal.

        Returns:
            True if the name is valid, False otherwise.
        """
        if not name or not isinstance(name, str):
            return False

        if not (name[0].isalpha() or name[0] == "_"):
            return False

        if not all(c.isalnum() or c == "_" for c in name[1:]):
            return False

        if keyword.iskeyword(name):
            return False

        return True

    @staticmethod
    def is_sympy_builtin(name: str) -> bool:
        """Check if a variable name is a SymPy built-in constant.

        Returns:
            True if the name is a SymPy built-in constant.
        """
        import sympy as sp

        builtin_constants = {
            "pi",
            "E",
            "I",
            "oo",
            "zoo",
            "nan",
            "GoldenRatio",
            "EulerGamma",
            "Catalan",
        }

        if name in builtin_constants:
            return True

        return hasattr(sp, name) and not name.startswith("_")

    def get(self, name: str) -> Any:
        """Get a variable value, or None if not found."""
        return self._variables.get(name)

    def set(self, name: str, value: Any) -> None:
        """Set a variable value.

        Raises:
            ValueError: If the variable name is invalid.
        """
        if not self.validate_name(name):
            raise ValueError(f"Invalid variable name: '{name}'")
        self._variables[name] = value
        self._touch()

    def delete(self, name: str) -> bool:
        """Delete a variable.

        Returns:
            True if deleted, False if not found.
        """
        if name in self._variables:
            del self._variables[name]
            self._touch()
            return True
        return False

    def exists(self, name: str) -> bool:
        """Check if a variable exists."""
        return name in self._variables

    def list_all(self) -> Dict[str, Any]:
        """Get all variables as a dictionary."""
        return dict(self._variables)

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

        value = self._variables[old_name]
        del self._variables[old_name]
        self._variables[new_name] = value
        self._touch()
        return True

    def clear(self) -> None:
        """Clear all variables."""
        self._variables.clear()
        self._touch()

    def generate_unique_name(self, base: str = "var") -> str:
        """Generate a unique variable name based on ``base``."""
        counter = 1
        while True:
            name = f"{base}_{counter}"
            if name not in self._variables and self.validate_name(name):
                return name
            counter += 1
