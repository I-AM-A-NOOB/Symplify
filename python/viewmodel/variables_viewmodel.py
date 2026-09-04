# coding: utf-8
"""Variables viewmodel for the QML Symplify app.

Exposes the VariableManager as a QAbstractTableModel so the shadow
TableView renders a real multi-column table, plus CRUD slots for the
page's toolbar. All mutations emit granular row signals (insert /
dataChanged / remove) so views update in place instead of resetting
wholesale.
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
    """Table model of calculator variables.

    Columns: name / expression / type. The expression column shows the
    canonical sympy string for valid entries and the raw user input for
    invalid ones (whose value is NaN). The ``invalid`` role lets the view
    render invalid entries distinctly.
    """

    InvalidRole = Qt.UserRole + 1

    warningOccurred = Signal(str, str)

    def __init__(self, manager: VariableManager, log: Optional[LogViewModel] = None, parent=None):
        """Initialize the variables model."""
        super().__init__(parent)
        self._manager = manager
        self._log = log
        self._keys: list = []  # insertion-ordered variable names

    def roleNames(self):
        return {
            Qt.DisplayRole: b"display",
            self.InvalidRole: b"invalid",
        }

    def flags(self, index: QModelIndex):
        """Name and expression columns are editable (Qt edit protocol)."""
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.isValid() and index.column() < 2:
            return base | Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        """Handle inline edits from the TableView's edit delegate.

        Column 0 renames; column 1 re-parses the expression. An invalid
        expression is kept in the list as an invalid (NaN) entry so the
        user's input is never lost.
        """
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.EditRole):
            return False
        if index.column() >= 2:
            return False
        row = index.row()
        if row < 0 or row >= len(self._keys):
            return False
        name = self._keys[row]
        text = str(value)

        if index.column() == 0:
            if text == name:
                return True
            try:
                ok = self.rename(name, text)
                if ok:
                    self._log_info(f"Variable renamed: {name} -> {text}")
                    self._warn_builtin(text)
                return ok
            except Exception as e:
                self._log_error(f"Failed to rename variable: {e}")
                return False

        try:
            parsed = self._parse(text)
        except Exception as parse_err:
            self.save_invalid(name, text)
            self._log_warn(f"Variable '{name}' kept as invalid: {parse_err}")
            return True
        self.save(name, parsed)
        self._log_info(f"Variable updated: {name} = {parsed}")
        self._warn_builtin(name)
        return True

    def _parse(self, value_str: str) -> Any:
        """Parse an expression with the current variable snapshot."""
        result = Calculator().evaluate(value_str, self._manager.list_all())
        if not result.success:
            raise ValueError(f"Failed to parse value: {result.error}")
        return result.value

    def _log_info(self, message: str) -> None:
        if self._log is not None:
            self._log.add_info(message, "Variables")

    def _log_warn(self, message: str) -> None:
        if self._log is not None:
            self._log.add_warning(message, "Variables")

    def _log_error(self, message: str) -> None:
        if self._log is not None:
            self._log.add_error(message, "Variables")

    def _warn_builtin(self, name: str) -> None:
        if VariableManager.is_sympy_builtin(name):
            self.warningOccurred.emit(
                name, f"{name} is a SymPy built-in. You asked for it."
            )
            self._log_warn(f"{name} is a SymPy built-in")

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of variables."""
        return 0 if parent.isValid() else len(self._keys)

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the fixed column count (name, expression, type)."""
        return 0 if parent.isValid() else 3

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._keys):
            return None
        entry = self._manager.entry(self._keys[row])
        if entry is None:
            return None
        if role == Qt.DisplayRole:
            return (entry.name, entry.expr_str, entry.type_label)[index.column()]
        if role == self.InvalidRole:
            return not entry.valid
        return None

    def _after_mutation(self, name: str, is_new: bool) -> None:
        """Emit the granular signal for an upsert of ``name``."""
        if is_new:
            row = len(self._keys)
            self.beginInsertRows(QModelIndex(), row, row)
            self._keys.append(name)
            self.endInsertRows()
        else:
            row = self._keys.index(name)
            self.dataChanged.emit(
                self.index(row, 0), self.index(row, self.columnCount() - 1)
            )

    def save(self, name: str, value: Any) -> None:
        """Insert or update a valid entry, notifying granularly."""
        is_new = not self._manager.exists(name)
        self._manager.save(name, value)
        self._after_mutation(name, is_new)

    def save_invalid(self, name: str, raw_expr: str) -> None:
        """Insert or update an invalid (NaN) entry, notifying granularly."""
        is_new = not self._manager.exists(name)
        self._manager.save_invalid(name, raw_expr)
        self._after_mutation(name, is_new)

    def rename(self, old_name: str, new_name: str) -> bool:
        """Rename via the manager, notifying granularly."""
        if old_name not in self._keys:
            return False
        if not self._manager.rename(old_name, new_name):
            return False
        row = self._keys.index(old_name)
        self._keys[row] = new_name
        self.dataChanged.emit(
            self.index(row, 0), self.index(row, self.columnCount() - 1)
        )
        return True

    def remove(self, name: str) -> bool:
        """Remove an entry, notifying granularly. Returns True if removed."""
        if name not in self._keys:
            return False
        row = self._keys.index(name)
        self.beginRemoveRows(QModelIndex(), row, row)
        self._manager.delete(name)
        self._keys.pop(row)
        self.endRemoveRows()
        return True

    @Slot(int, int, result=QModelIndex)
    def modelIndex(self, row: int, column: int) -> QModelIndex:
        """Build a QModelIndex for QML (e.g. TableView.edit)."""
        return self.index(row, column)

    @Slot(int, int, result=str)
    def cellAt(self, row: int, column: int) -> str:
        """Return the cell text at (row, column), callable from QML."""
        if 0 <= row < len(self._keys) and 0 <= column < 3:
            entry = self._manager.entry(self._keys[row])
            if entry:
                return (entry.name, entry.expr_str, entry.type_label)[column]
        return ""

    @Slot(int, result=str)
    def nameAt(self, row: int) -> str:
        """Return the variable name at ``row`` (or empty string)."""
        return self.cellAt(row, 0)

    @Slot(result=int)
    def count(self) -> int:
        """Number of rows, callable from QML."""
        return len(self._keys)


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
        self._model = VariablesModel(variable_manager, log, parent=self)
        self._model.warningOccurred.connect(self.warningOccurred)

    def _get_model(self) -> VariablesModel:
        return self._model

    model = Property(QObject, _get_model, constant=True)

    @Slot(str, str, result=bool)
    def addVariable(self, name: str, value_str: str) -> bool:
        """Add a variable, parsing the value expression."""
        try:
            parsed = self._parse_value(value_str)
            self._model.save(name, parsed)
            self._log.add_info(f"Variable added: {name} = {parsed}", "Variables")
            self._warn_if_builtin(name)
            return True
        except Exception as e:
            self._log.add_error(f"Failed to add variable: {e}", "Variables")
            return False

    @Slot(str, result=bool)
    def deleteVariable(self, name: str) -> bool:
        """Delete a variable."""
        if self._model.remove(name):
            self._log.add_info(f"Variable deleted: {name}", "Variables")
            return True
        return False

    @Slot(str, str, result=bool)
    def renameVariable(self, old_name: str, new_name: str) -> bool:
        """Rename a variable."""
        try:
            ok = self._model.rename(old_name, new_name)
            if ok:
                self._log.add_info(
                    f"Variable renamed: {old_name} -> {new_name}", "Variables"
                )
                self._warn_if_builtin(new_name)
            return ok
        except Exception as e:
            self._log.add_error(f"Failed to rename variable: {e}", "Variables")
            return False

    @Slot(str, str, result=bool)
    def updateVariable(self, name: str, value_str: str) -> bool:
        """Update a variable's value.

        An invalid expression is kept in the list as an invalid (NaN)
        entry so the user's input is never lost.
        """
        try:
            if not self._variable_manager.exists(name):
                self._log.add_error(f"Variable '{name}' does not exist", "Variables")
                return False
            try:
                parsed = self._parse_value(value_str)
            except Exception as parse_err:
                self._model.save_invalid(name, value_str)
                self._log.add_warning(
                    f"Variable '{name}' kept as invalid: {parse_err}", "Variables"
                )
                return True
            self._model.save(name, parsed)
            self._log.add_info(f"Variable updated: {name} = {parsed}", "Variables")
            self._warn_if_builtin(name)
            return True
        except Exception as e:
            self._log.add_error(f"Failed to update variable: {e}", "Variables")
            return False

    @Slot(result=str)
    def generateUniqueName(self) -> str:
        """Generate a unique default variable name."""
        return self._variable_manager.generate_unique_name("var")

    def _warn_if_builtin(self, name: str) -> None:
        """Emit the built-in warning if ``name`` shadows a SymPy constant."""
        if VariableManager.is_sympy_builtin(name):
            self.warningOccurred.emit(
                name, f"{name} is a SymPy built-in. You asked for it."
            )

    def _parse_value(self, value_str: str) -> Any:
        """Parse a value string through the Calculator."""
        if isinstance(value_str, str):
            calc = Calculator()
            result = calc.evaluate(value_str, self._variable_manager.list_all())
            if not result.success:
                raise ValueError(f"Failed to parse value: {result.error}")
            return result.value
        return value_str
