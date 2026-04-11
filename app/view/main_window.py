# coding: utf-8
"""Main window for the Symplify calculator application.

This module provides the main application window using FluentWindow,
containing the calculator and variables interfaces with their ViewModels.

Example:
    >>> from PySide6.QtWidgets import QApplication
    >>> app = QApplication([])
    >>> window = MainWindow()
    >>> window.show()
"""

from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import (
    FluentWindow,
    FluentIcon,
    NavigationItemPosition,
    SystemThemeListener,
)

from ..viewmodel import MainWindowViewModel
from ..viewmodel.settings_viewmodel import SettingsViewModel
from ..model import Calculator, VariableManager
from ..common.ui_utils import InfoBarHelper


class MainWindow(FluentWindow):
    """Main application window for Symplify calculator.

    A FluentWindow-based main window that hosts the calculator and
    variables interfaces with their ViewModels.

    Attributes:
        viewmodel: The MainWindow ViewModel.

    Example:
        >>> window = MainWindow()
        >>> window.show()
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the main window."""
        super().__init__(parent)
        self._create_viewmodel()
        self._setup_window()
        self._create_interfaces()
        self._init_navigation()
        self._setup_system_theme_listener()

    def _create_viewmodel(self) -> None:
        """Create the main window ViewModel."""
        calculator = Calculator()
        variable_manager = VariableManager()
        self.viewmodel = MainWindowViewModel(calculator, variable_manager, parent=self)

    def _setup_window(self) -> None:
        """Configure window properties and styling."""
        self.setWindowTitle("Symplify - SymPy Algebra Calculator")
        self.setWindowIcon(QIcon())
        self.resize(1280, 720)
        self.setMinimumSize(640, 480)
        self._center_window()

    def _center_window(self) -> None:
        """Center the window on the primary screen."""
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def _create_interfaces(self) -> None:
        """Create sub-interfaces and connect to ViewModels."""
        from .calculator_interface import CalculatorInterface
        from .variables_interface import VariablesInterface
        from .log_interface import LogInterface
        from .history_interface import HistoryInterface
        from .settings_interface import SettingsInterface

        # Create interfaces
        self.calculator_interface = CalculatorInterface(self)
        self.calculator_interface.setObjectName("CalculatorInterface")
        self.variables_interface = VariablesInterface(self)
        self.variables_interface.setObjectName("VariablesInterface")
        self.log_interface = LogInterface(self)
        self.log_interface.setObjectName("LogInterface")
        self.history_interface = HistoryInterface(self)
        self.history_interface.setObjectName("HistoryInterface")
        self.settings_interface = SettingsInterface(parent=self)
        self.settings_interface.setObjectName("SettingsInterface")

        # Connect signals
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect all signals between View and ViewModel."""
        calc_vm = self.viewmodel.calculator_viewmodel
        var_vm = self.viewmodel.variables_viewmodel

        # Calculator interface
        self.calculator_interface.calculate_requested.connect(calc_vm.calculate)
        self.calculator_interface.example_selected.connect(
            self.calculator_interface.set_input_text
        )
        self.calculator_interface.expression_copied.connect(
            lambda: InfoBarHelper.show_info(
                self, self.tr("Copied"), self.tr("Expression copied to clipboard")
            )
        )
        self.calculator_interface.latex_copied.connect(
            lambda: InfoBarHelper.show_info(
                self, self.tr("Copied"), self.tr("LaTeX copied to clipboard")
            )
        )
        calc_vm.result_ready.connect(self._on_calculation_result)
        calc_vm.error_occurred.connect(self._on_error)

        # Variables interface
        self.variables_interface.variable_add_requested.connect(self._on_add_variable)
        self.variables_interface.variable_delete_requested.connect(
            var_vm.delete_variable
        )
        self.variables_interface.variable_edit_requested.connect(var_vm.update_variable)
        self.variables_interface.variable_rename_requested.connect(
            var_vm.rename_variable
        )
        var_vm.variables_updated.connect(
            lambda: self.variables_interface.set_variables(var_vm.get_variables())
        )
        var_vm.error_occurred.connect(self._on_error)

        # Log interface
        self.viewmodel.log_updated.connect(self.log_interface.set_log_content)
        self.log_interface.set_log_content(
            self.viewmodel.log_viewmodel.get_formatted_logs()
        )

        # History interface
        self.viewmodel.history_updated.connect(
            lambda: self.history_interface.set_history_items(
                self.viewmodel.history_viewmodel.get_history()
            )
        )
        self.history_interface.clear_button.clicked.connect(
            self.viewmodel.history_viewmodel.clear
        )

    def _init_navigation(self) -> None:
        """Initialize the navigation interface."""
        self.addSubInterface(
            self.calculator_interface,
            FluentIcon.SEND,
            self.tr("Calculator"),
            NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.variables_interface,
            FluentIcon.VIEW,
            self.tr("Variables"),
            NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.history_interface,
            FluentIcon.HISTORY,
            self.tr("History"),
            NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.log_interface,
            FluentIcon.MESSAGE,
            self.tr("Log"),
            NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(
            self.settings_interface,
            FluentIcon.SETTING,
            self.tr("Settings"),
            NavigationItemPosition.BOTTOM,
        )
        self.navigationInterface.setAcrylicEnabled(True)

    def _on_calculation_result(self, result) -> None:
        """Handle calculation result."""
        if result.success:
            self.calculator_interface.show_latex_result(result.latex)
            if result.data_points:
                try:
                    self.calculator_interface.plot_data(result.data_points)
                except Exception as e:
                    self.viewmodel.log_viewmodel.add_warning(
                        f"Plot error: {e}", "MainWindow"
                    )
        else:
            self._on_error(result.error)

    def _on_add_variable(self) -> None:
        """Handle add variable request."""
        name, success = self.viewmodel.add_variable_with_default()
        if success:
            InfoBarHelper.show_success(
                self, self.tr("Success"), self.tr(f"Variable '{name}' added")
            )

    def _on_error(self, message: str) -> None:
        """Show error message."""
        InfoBarHelper.show_error(self, self.tr("Error"), message)

    def _setup_system_theme_listener(self) -> None:
        """Setup listener for system theme changes.

        When system theme changes and app is set to AUTO mode,
        the theme will automatically update.
        """
        self.theme_listener = SystemThemeListener(self)
        self.theme_listener.start()

    def closeEvent(self, event) -> None:
        """Handle window close event.

        Cleans up system theme listener resources.
        """
        self.theme_listener.terminate()
        self.theme_listener.deleteLater()
        super().closeEvent(event)
