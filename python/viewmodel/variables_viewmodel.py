# coding: utf-8
"""Variables viewmodel for the QML Symplify app.

Exposes the VariableManager as a QAbstractTableModel so the Qt Quick
Controls TableView renders a real multi-column table, plus CRUD slots
for the page's toolbar. The widgets app's EventBus wiring and dead
accessors (``get_variable_list``, ``validate_name``, ``clear_all``)
are not carried over.
"""

from typing import Any, Optional

from PySide6.QtCore import (
    Property,
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    Signal,
    Slot,
)

from ..model.calculator import Calculator
from ..model.variable import VariableManager
from .log_viewmodel import LogViewModel


class VariablesModel(QAbstractTableModel):
    """Table model of calculator variables (columns: name, value).

    Cell data is served from a cached ``(name, value_str)`` list so reads
    are O(1) instead of rebuilding the manager dict per call. The cache is
    refreshed on ``refresh()`` and lazily validated against the manager's
    ``revision`` counter.
    """

    NameRole = Qt.UserRole + 1
    ValueRole = Qt.UserRole + 2

    def __init__(self, manager: VariableManager, parent=None):
        """Initialize the variables model."""
        super().__init__(parent)
        self._manager = manager
        self._items: list = []  # list of (name, value_str)
        self._revision: int = -1

    def roleNames(self):
        return {
            self.NameRole: b"name",
            self.ValueRole: b"value",
        }

    def _ensure_cache(self) -> None:
        """Rebuild the cached items if the manager changed since last build."""
        if self._revision != self._manager.revision:
            self._items = [
                (name, str(value))
                for name, value in self._manager.list_all().items()
            ]
            self._revision = self._manager.revision

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of variables."""
        if parent.isValid():
            return 0
        self._ensure_cache()
        return len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the fixed column count (name, value)."""
        return 0 if parent.isValid() else 2

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid():
            return None
        self._ensure_cache()
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        name, value = self._items[row]
        if role == self.NameRole or (role == Qt.DisplayRole and index.column() == 0):
            return name
        if role == self.ValueRole or (role == Qt.DisplayRole and index.column() == 1):
            return value
        return None

    @Slot(int, result=str)
    def nameAt(self, row: int) -> str:
        """Return the variable name at ``row`` (or empty string)."""
        self._ensure_cache()
        return self._items[row][0] if 0 <= row < len(self._items) else ""

    @Slot(int, result=str)
    def valueAt(self, row: int) -> str:
        """Return the variable value string at ``row`` (or empty string)."""
        self._ensure_cache()
        return self._items[row][1] if 0 <= row < len(self._items) else ""

    def refresh(self) -> None:
        """Rebuild the model after a change."""
        self._ensure_cache()
        self.beginResetModel()
        self.endResetModel()


class VariablesViewModel(QObject):
    """Connects the VariableManager model to the QML variables page.

    Signals:
        warningOccurred: Emitted when the user names a variable after a
            SymPy built-in. Args: title (str), content (str).
    """

    warningOccurred = Signal(str, str)

    def __init__(
        self,
        variable_manager: VariableManager,
        log: LogViewModel,
        parent: Optional[QObject] = None,
    ):
        """Initialize the variables viewmodel."""
        super().__init__(parent)
        self._variable_manager = variable_manager
        self._log = log
        self._model = VariablesModel(variable_manager, parent=self)

    def _get_model(self) -> VariablesModel:
        return self._model

    model = Property(QObject, _get_model, constant=True)

    @Slot(str, str, result=bool)
    def addVariable(self, name: str, value_str: str) -> bool:
        """Add a variable, parsing the value expression."""
        try:
            parsed = self._parse_value(value_str)
            self._variable_manager.set(name, parsed)
            self._model.refresh()
            self._log.add_info(f"Variable added: {name} = {parsed}", "Variables")
            return True
        except Exception as e:
            self._log.add_error(f"Failed to add variable: {e}", "Variables")
            return False

    @Slot(str, result=bool)
    def deleteVariable(self, name: str) -> bool:
        """Delete a variable."""
        if self._variable_manager.delete(name):
            self._model.refresh()
            self._log.add_info(f"Variable deleted: {name}", "Variables")
            return True
        return False

    @Slot(str, str, result=bool)
    def renameVariable(self, old_name: str, new_name: str) -> bool:
        """Rename a variable."""
        try:
            ok = self._variable_manager.rename(old_name, new_name)
            if ok:
                self._model.refresh()
                self._log.add_info(
                    f"Variable renamed: {old_name} -> {new_name}", "Variables"
                )
                if VariableManager.is_sympy_builtin(new_name):
                    self.warningOccurred.emit(
                        new_name,
                        f"{new_name} is a SymPy built-in. You asked for it.",
                    )
            return ok
        except Exception as e:
            self._log.add_error(f"Failed to rename variable: {e}", "Variables")
            return False

    @Slot(str, str, result=bool)
    def updateVariable(self, name: str, value_str: str) -> bool:
        """Update a variable's value."""
        try:
            if not self._variable_manager.exists(name):
                self._log.add_error(f"Variable '{name}' does not exist", "Variables")
                return False
            parsed = self._parse_value(value_str)
            self._variable_manager.set(name, parsed)
            self._model.refresh()
            self._log.add_info(f"Variable updated: {name} = {parsed}", "Variables")
            if VariableManager.is_sympy_builtin(name):
                self.warningOccurred.emit(
                    name, f"{name} is a SymPy built-in. You asked for it."
                )
            return True
        except Exception as e:
            self._log.add_error(f"Failed to update variable: {e}", "Variables")
            return False

    @Slot(result=str)
    def generateUniqueName(self) -> str:
        """Generate a unique default variable name."""
        return self._variable_manager.generate_unique_name("var")

    def _parse_value(self, value_str: str) -> Any:
        """Parse a value string through the Calculator."""
        if isinstance(value_str, str):
            calc = Calculator()
            result = calc.evaluate(value_str, self._variable_manager.list_all())
            if not result.success:
                raise ValueError(f"Failed to parse value: {result.error}")
            return result.value
        return value_str
