# coding: utf-8
"""Variables management interface for the Symplify application.

This module provides the variables interface view for viewing and managing
calculator variables in a table format.

Example:
    >>> from app.view.variables_interface import VariablesInterface
    >>> interface = VariablesInterface()
    >>> interface.show()
"""
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QAbstractItemView,
    QTableWidgetItem,
)
from qfluentwidgets import (
    SubtitleLabel,
    TableWidget,
    CommandBar,
    TransparentToolButton,
    FluentIcon,
    InfoBar,
)


class VariablesInterface(QWidget):
    """Variables management interface view.

    Provides a table-based interface for viewing and managing calculator
    variables. Follows MVVM pattern - contains only view logic.

    Signals:
        variable_add_requested: Emitted when user wants to add a variable.
        variable_delete_requested: Emitted when user wants to delete a variable.
            Args:
                name (str): Name of the variable to delete.
        variable_edit_requested: Emitted when user edits a variable.
            Args:
                name (str): Variable name.
                value (str): New value.
        variable_rename_requested: Emitted when user renames a variable.
            Args:
                old_name (str): Original variable name.
                new_name (str): New variable name.

    Attributes:
        table: The table widget displaying variables.

    Example:
        >>> interface = VariablesInterface()
        >>> interface.variable_add_requested.connect(handle_add)
    """

    variable_add_requested = Signal()
    variable_delete_requested = Signal(str)
    variable_edit_requested = Signal(str, str)
    variable_rename_requested = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the variables interface.

        Args:
            parent: The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self._original_var_name: Optional[str] = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setContentsMargins(8, 8, 8, 8)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Title
        self.title_label = SubtitleLabel(self.tr("Variables"), self)
        layout.addWidget(self.title_label)

        # Variables table
        self.table = TableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([
            self.tr("Name"),
            self.tr("Value"),
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Toolbar
        self._setup_toolbar()
        layout.addWidget(self.toolbar)

    def _setup_toolbar(self) -> None:
        """Set up the toolbar with action buttons."""
        self.toolbar = CommandBar(self)

        # Add button
        self.add_button = TransparentToolButton(FluentIcon.ADD, self)
        self.add_button.setToolTip(self.tr("Add variable"))
        self.toolbar.addWidget(self.add_button)

        # Delete button
        self.delete_button = TransparentToolButton(FluentIcon.REMOVE, self)
        self.delete_button.setToolTip(self.tr("Delete selected variable"))
        self.toolbar.addWidget(self.delete_button)

        # Edit button
        self.edit_button = TransparentToolButton(FluentIcon.EDIT, self)
        self.edit_button.setToolTip(self.tr("Edit selected variable"))
        self.toolbar.addWidget(self.edit_button)

        # Rename button
        self.rename_button = TransparentToolButton(FluentIcon.FONT, self)
        self.rename_button.setToolTip(self.tr("Rename selected variable"))
        self.toolbar.addWidget(self.rename_button)

    def _connect_signals(self) -> None:
        """Connect UI signals to slots."""
        # Toolbar buttons
        self.add_button.clicked.connect(self.variable_add_requested.emit)
        self.delete_button.clicked.connect(self._on_delete)
        self.edit_button.clicked.connect(self._on_edit)
        self.rename_button.clicked.connect(self._on_rename)

        # Table signals
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def _on_delete(self) -> None:
        """Handle delete button click."""
        row = self.table.currentRow()
        if row >= 0:
            name_item = self.table.item(row, 0)
            if name_item:
                var_name = name_item.text()
                self.variable_delete_requested.emit(var_name)
        else:
            self.show_warning(
                self.tr("Warning"),
                self.tr("Please select a variable to delete")
            )

    def _on_edit(self) -> None:
        """Handle edit button click."""
        row = self.table.currentRow()
        if row >= 0:
            self.table.editItem(self.table.item(row, 1))
        else:
            self.show_warning(
                self.tr("Warning"),
                self.tr("Please select a variable to edit")
            )

    def _on_rename(self) -> None:
        """Handle rename button click."""
        row = self.table.currentRow()
        if row >= 0:
            name_item = self.table.item(row, 0)
            if name_item:
                self._original_var_name = name_item.text()
                self.table.editItem(name_item)
        else:
            self.show_warning(
                self.tr("Warning"),
                self.tr("Please select a variable to rename")
            )

    def _on_cell_changed(self, row: int, column: int) -> None:
        """Handle table cell changes.

        Args:
            row: The row index.
            column: The column index.
        """
        if column == 0:  # Name column - rename
            new_name = self.table.item(row, 0).text()
            if self._original_var_name and self._original_var_name != new_name:
                self.variable_rename_requested.emit(
                    self._original_var_name, new_name
                )
                self._original_var_name = None
        elif column == 1:  # Value column - edit
            name = self.table.item(row, 0).text()
            value = self.table.item(row, 1).text()
            self.variable_edit_requested.emit(name, value)

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        """Handle table cell double click.

        Args:
            row: The row index.
            column: The column index.
        """
        if column == 0:  # Name column
            name_item = self.table.item(row, 0)
            if name_item:
                self._original_var_name = name_item.text()

    # Public API for ViewModel binding

    def set_variables(self, variables: Dict[str, Any]) -> None:
        """Set the variables to display in the table.

        Args:
            variables: Dictionary mapping variable names to values.
        """
        # Block signals during update
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(variables))
            for i, (name, value) in enumerate(variables.items()):
                # Name column
                name_item = QTableWidgetItem(str(name))
                name_item.setFlags(
                    name_item.flags() | Qt.ItemFlag.ItemIsEditable
                )
                self.table.setItem(i, 0, name_item)

                # Value column
                value_str = self._format_value(value)
                value_item = QTableWidgetItem(value_str)
                value_item.setFlags(
                    value_item.flags() | Qt.ItemFlag.ItemIsEditable
                )
                self.table.setItem(i, 1, value_item)
        finally:
            self.table.blockSignals(False)

    def _format_value(self, value: Any) -> str:
        """Format a variable value for display.

        Args:
            value: The value to format.

        Returns:
            Formatted string representation.
        """
        try:
            return str(value)
        except Exception:
            return "<unrepresentable>"

    def get_selected_variable(self) -> Optional[str]:
        """Get the name of the currently selected variable.

        Returns:
            The variable name, or None if no selection.
        """
        row = self.table.currentRow()
        if row >= 0:
            name_item = self.table.item(row, 0)
            if name_item:
                return name_item.text()
        return None

    def show_info(self, title: str, content: str, duration: int = 2000) -> None:
        """Show an info message.

        Args:
            title: The message title.
            content: The message content.
            duration: Display duration in milliseconds. Defaults to 2000.
        """
        InfoBar.info(title=title, content=content, parent=self, duration=duration)

    def show_warning(self, title: str, content: str, duration: int = 2000) -> None:
        """Show a warning message.

        Args:
            title: The warning title.
            content: The warning content.
            duration: Display duration in milliseconds. Defaults to 2000.
        """
        InfoBar.warning(title=title, content=content, parent=self, duration=duration)

    def show_error(self, title: str, content: str, duration: int = 2000) -> None:
        """Show an error message.

        Args:
            title: The error title.
            content: The error content.
            duration: Display duration in milliseconds. Defaults to 2000.
        """
        InfoBar.error(title=title, content=content, parent=self, duration=duration)
