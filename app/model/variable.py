# coding: utf-8
"""Variable management model for the calculator.

This module provides variable storage and management functionality,
completely separate from the view layer.

Example:
    >>> from app.model.variable import VariableManager
    >>> vm = VariableManager()
    >>> vm.set("x", 42)
    >>> print(vm.get("x"))
    42
"""
import keyword
import re
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class Variable:
    """Represents a single variable.
    
    Attributes:
        name: The variable name.
        value: The variable value.
        
    Example:
        >>> var = Variable(name="x", value=42)
        >>> print(var.name)
        x
    """
    name: str
    value: Any


class VariableManager:
    """Manages calculator variables.
    
    Provides CRUD operations for variables with name validation.
    Independent of any UI.
    
    Attributes:
        _variables: Dictionary storing variable name-value pairs.
        _observers: List of observer callbacks.
        
    Example:
        >>> vm = VariableManager()
        >>> vm.set("pi", 3.14159)
        >>> vm.set("x", 10)
        >>> print(vm.list_all())
        {'pi': 3.14159, 'x': 10}
    """
    
    def __init__(self):
        """Initialize the variable manager."""
        self._variables: Dict[str, Any] = {}
        self._observers: List[Callable[[str, Any], None]] = []
    
    def validate_name(self, name: str) -> bool:
        """Validate if a variable name is legal.
        
        Args:
            name: The variable name to validate.
            
        Returns:
            True if the name is valid, False otherwise.
            
        Example:
            >>> vm = VariableManager()
            >>> vm.validate_name("x")
            True
            >>> vm.validate_name("123")
            False
            >>> vm.validate_name("for")
            False
        """
        if not name or not isinstance(name, str):
            return False
        
        # Must start with letter or underscore
        if not (name[0].isalpha() or name[0] == "_"):
            return False
        
        # Rest must be alphanumeric or underscore
        if not all(c.isalnum() or c == "_" for c in name[1:]):
            return False
        
        # Cannot be Python keyword
        if keyword.iskeyword(name):
            return False
        
        return True
    
    def get(self, name: str) -> Any:
        """Get a variable value.
        
        Args:
            name: The variable name.
            
        Returns:
            The variable value, or None if not found.
            
        Example:
            >>> vm = VariableManager()
            >>> vm.set("x", 42)
            >>> vm.get("x")
            42
            >>> vm.get("y") is None
            True
        """
        return self._variables.get(name)
    
    def set(self, name: str, value: Any) -> None:
        """Set a variable value.
        
        Args:
            name: The variable name.
            value: The value to set.
            
        Raises:
            ValueError: If the variable name is invalid.
            
        Example:
            >>> vm = VariableManager()
            >>> vm.set("x", 42)
            >>> vm.get("x")
            42
        """
        if not self.validate_name(name):
            raise ValueError(f"Invalid variable name: '{name}'")
        
        self._variables[name] = value
        self._notify_observers("set", name, value)
    
    def delete(self, name: str) -> bool:
        """Delete a variable.
        
        Args:
            name: The variable name to delete.
            
        Returns:
            True if deleted, False if not found.
            
        Example:
            >>> vm = VariableManager()
            >>> vm.set("x", 42)
            >>> vm.delete("x")
            True
            >>> vm.delete("x")
            False
        """
        if name in self._variables:
            del self._variables[name]
            self._notify_observers("delete", name, None)
            return True
        return False
    
    def exists(self, name: str) -> bool:
        """Check if a variable exists.
        
        Args:
            name: The variable name.
            
        Returns:
            True if the variable exists.
            
        Example:
            >>> vm = VariableManager()
            >>> vm.set("x", 42)
            >>> vm.exists("x")
            True
            >>> vm.exists("y")
            False
        """
        return name in self._variables
    
    def list_all(self) -> Dict[str, Any]:
        """Get all variables as a dictionary.
        
        Returns:
            Dictionary of all variables.
            
        Example:
            >>> vm = VariableManager()
            >>> vm.set("x", 1)
            >>> vm.set("y", 2)
            >>> vm.list_all()
            {'x': 1, 'y': 2}
        """
        return dict(self._variables)
    
    def list_variables(self) -> List[Variable]:
        """Get all variables as a list.
        
        Returns:
            List of Variable objects.
            
        Example:
            >>> vm = VariableManager()
            >>> vm.set("x", 1)
            >>> vm.list_variables()
            [Variable(name='x', value=1)]
        """
        return [Variable(name=k, value=v) for k, v in self._variables.items()]
    
    def rename(self, old_name: str, new_name: str) -> bool:
        """Rename a variable.
        
        Args:
            old_name: The current variable name.
            new_name: The new variable name.
            
        Returns:
            True if renamed successfully.
            
        Raises:
            ValueError: If the new name is invalid or already exists.
            
        Example:
            >>> vm = VariableManager()
            >>> vm.set("x", 42)
            >>> vm.rename("x", "y")
            True
            >>> vm.get("y")
            42
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
        
        self._notify_observers("rename", new_name, value)
        return True
    
    def clear(self) -> None:
        """Clear all variables.
        
        Example:
            >>> vm = VariableManager()
            >>> vm.set("x", 1)
            >>> vm.clear()
            >>> vm.list_all()
            {}
        """
        self._variables.clear()
        self._notify_observers("clear", "", None)
    
    def generate_unique_name(self, base: str = "var") -> str:
        """Generate a unique variable name.
        
        Args:
            base: The base name. Defaults to "var".
            
        Returns:
            A unique variable name.
            
        Example:
            >>> vm = VariableManager()
            >>> vm.set("var_1", 1)
            >>> vm.generate_unique_name("var")
            'var_2'
        """
        counter = 1
        while True:
            name = f"{base}_{counter}"
            if name not in self._variables and self.validate_name(name):
                return name
            counter += 1
    
    def add_observer(self, callback: Callable[[str, Any], None]) -> None:
        """Add an observer callback.
        
        Args:
            callback: Function to call when variables change.
            
        Example:
            >>> vm = VariableManager()
            >>> def on_change(event, data):
            ...     print(f"Event: {event}")
            >>> vm.add_observer(on_change)
        """
        self._observers.append(callback)
    
    def remove_observer(self, callback: Callable[[str, Any], None]) -> None:
        """Remove an observer callback.
        
        Args:
            callback: The callback to remove.
        """
        if callback in self._observers:
            self._observers.remove(callback)
    
    def _notify_observers(self, event: str, name: str, value: Any) -> None:
        """Notify all observers of a change.
        
        Args:
            event: The event type.
            name: The variable name.
            value: The variable value.
        """
        for observer in self._observers:
            try:
                observer(event, {"name": name, "value": value})
            except Exception:
                # Ignore observer errors
                pass
