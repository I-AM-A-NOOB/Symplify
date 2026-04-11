# coding: utf-8
"""Calculator interface for the Symplify application.

This module provides the calculator interface view, containing input panel,
keyboard panel, documentation panel, and result display area.

Example:
    >>> from app.view.calculator_interface import CalculatorInterface
    >>> interface = CalculatorInterface()
    >>> interface.show()
"""

from typing import Optional, List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QSizePolicy,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSpacerItem,
)
from qfluentwidgets import (
    CommandBar,
    TransparentToolButton,
    TransparentDropDownPushButton,
    FluentIcon,
    TextEdit,
    StrongBodyLabel,
    RoundMenu,
    Action,
    InfoBar,
    ToolTipFilter,
    ToolTipPosition,
    SegmentedWidget,
    PrimaryPushButton,
)

from ..qfluentplus import Splitter, LaTeXLabel, MathPlotWidget
from ..common.input_mode import InputMode
from ..components import KeyboardPanel
from ..viewmodel import KeyboardViewModel


class CalculatorInterface(QWidget):
    """Calculator interface view.

    Provides the main calculator UI with input area, keyboard, documentation,
    and result display. Follows MVVM pattern - contains only view logic.

    Signals:
        calculate_requested: Emitted when user requests calculation.
            Args:
                expression (str): The expression to calculate.
                mode (InputMode): The input mode.
        example_selected: Emitted when user selects an example.
            Args:
                expression (str): The selected example expression.
        copy_expression_requested: Emitted when user wants to copy expression.
        copy_latex_requested: Emitted when user wants to copy LaTeX.

    Attributes:
        input_field: The main input text edit.
        result_display: The result display text edit.
        expression_label: Label showing current expression.

    Example:
        >>> interface = CalculatorInterface()
        >>> interface.calculate_requested.connect(handle_calculation)
    """

    calculate_requested = Signal(str, InputMode)
    example_selected = Signal(str)
    expression_copied = Signal(str)
    latex_copied = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the calculator interface.

        Args:
            parent: The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self._current_mode = InputMode.CODE
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._setup_keyboard()

        # Focus input field on startup
        self._focus_input()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setContentsMargins(8, 8, 8, 8)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Command bar
        self._setup_command_bar()
        main_layout.addWidget(self.command_bar)

        # Splitter for left/right panels
        self.splitter = Splitter(Qt.Orientation.Horizontal)
        self.splitter.setContentsMargins(10, 10, 10, 10)

        # Setup panels
        left_widget = self._setup_left_panel()
        right_widget = self._setup_right_panel()

        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.splitter)

    def _setup_command_bar(self) -> None:
        """Set up the command bar with action buttons."""
        self.command_bar = CommandBar(self)

        # Calculate button (primary)
        self.calc_button = PrimaryPushButton(self.tr("Calculate"), self)
        self.calc_button.setIcon(FluentIcon.SEND)
        self.command_bar.addWidget(self.calc_button)

        self.command_bar.addSeparator()

        # Clear button
        self.clear_button = TransparentToolButton(FluentIcon.DELETE, self)
        self.clear_button.setToolTip(self.tr("Clear input"))
        self.clear_button.installEventFilter(
            ToolTipFilter(self.clear_button, 300, ToolTipPosition.TOP)
        )
        self.command_bar.addWidget(self.clear_button)

        # Undo button
        self.undo_button = TransparentToolButton(FluentIcon.LEFT_ARROW, self)
        self.undo_button.setToolTip(self.tr("Undo"))
        self.undo_button.installEventFilter(
            ToolTipFilter(self.undo_button, 300, ToolTipPosition.TOP)
        )
        self.command_bar.addWidget(self.undo_button)

        # Redo button
        self.redo_button = TransparentToolButton(FluentIcon.RIGHT_ARROW, self)
        self.redo_button.setToolTip(self.tr("Redo"))
        self.redo_button.installEventFilter(
            ToolTipFilter(self.redo_button, 300, ToolTipPosition.TOP)
        )
        self.command_bar.addWidget(self.redo_button)

        self.command_bar.addSeparator()

        # Examples dropdown button
        self.example_button = TransparentDropDownPushButton(self.tr("Examples"), self)
        self.command_bar.addWidget(self.example_button)

    def _setup_left_panel(self) -> QWidget:
        """Set up the left panel with input and controls.

        Returns:
            The left panel widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Input mode selector
        self._setup_mode_selector(layout)

        # Input area
        self.input_field = TextEdit(self)
        self.input_field.setPlaceholderText(self.tr("Enter expression..."))
        self.input_field.setMaximumHeight(120)
        self.input_field.installEventFilter(self)
        layout.addWidget(self.input_field)

        # Keyboard panel
        self.keyboard_panel = KeyboardPanel(self)
        layout.addWidget(self.keyboard_panel)

        # Spacer at bottom
        layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        return widget

    def _setup_mode_selector(self, parent_layout: QVBoxLayout) -> None:
        """Set up the input mode selector.

        Args:
            parent_layout: The parent layout to add to.
        """
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)

        # Mode label
        mode_label = StrongBodyLabel(self.tr("Mode:"), self)
        mode_layout.addWidget(mode_label)

        # Segmented widget for mode selection
        self.mode_selector = SegmentedWidget(self)
        self.mode_selector.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.mode_selector.addItem("code", self.tr("Code"))
        self.mode_selector.addItem("assign", self.tr("Assign"))
        self.mode_selector.setCurrentItem("code")
        self.mode_selector.currentItemChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_selector)

        self.mode_spacer = QSpacerItem(
            0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        mode_layout.addItem(self.mode_spacer)

        mode_layout.addStretch()
        parent_layout.addLayout(mode_layout)

    def _setup_right_panel(self) -> QWidget:
        """Set up the right panel with result display.

        Returns:
            The right panel widget.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Expression area with copy buttons
        self._setup_expression_area(layout)

        # Result stack (LaTeX / Plot)
        self._setup_result_stack(layout)

        return widget

    def _setup_expression_area(self, parent_layout: QVBoxLayout) -> None:
        """Set up the expression display area with copy buttons.

        Args:
            parent_layout: The parent layout to add to.
        """
        # Expression container
        expr_container = QWidget(self)
        expr_layout = QHBoxLayout(expr_container)
        expr_layout.setContentsMargins(0, 0, 0, 0)
        expr_layout.setSpacing(8)

        # Expression label
        self.expression_label = StrongBodyLabel("", self)
        self.expression_label.setWordWrap(True)
        self.expression_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        expr_layout.addWidget(self.expression_label, stretch=1)

        # Copy expression button
        self.copy_expr_button = TransparentToolButton(FluentIcon.COPY, self)
        self.copy_expr_button.setToolTip(self.tr("Copy expression"))
        self.copy_expr_button.installEventFilter(
            ToolTipFilter(self.copy_expr_button, 300, ToolTipPosition.TOP)
        )
        expr_layout.addWidget(self.copy_expr_button)

        # Copy LaTeX button
        self.copy_latex_button = TransparentToolButton(FluentIcon.PASTE, self)
        self.copy_latex_button.setToolTip(self.tr("Copy LaTeX"))
        self.copy_latex_button.installEventFilter(
            ToolTipFilter(self.copy_latex_button, 300, ToolTipPosition.TOP)
        )
        expr_layout.addWidget(self.copy_latex_button)

        parent_layout.addWidget(expr_container)

    def _setup_result_stack(self, parent_layout: QVBoxLayout) -> None:
        """Set up the result display area with LaTeX and Plot.

        Args:
            parent_layout: The parent layout to add to.
        """
        # Result container with LaTeX on top and Plot below
        result_container = QWidget(self)
        result_layout = QVBoxLayout(result_container)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(8)

        # LaTeX result area (top)
        latex_container = QWidget(self)
        latex_layout = QVBoxLayout(latex_container)
        latex_layout.setContentsMargins(0, 0, 0, 0)

        self.latex_label = LaTeXLabel("", self)
        self.latex_label.setMinimumHeight(80)
        latex_layout.addWidget(self.latex_label)

        result_layout.addWidget(latex_container)

        # Plot area (bottom)
        self.plot_widget = MathPlotWidget(self, show_toolbar=True)
        result_layout.addWidget(self.plot_widget, stretch=1)

        parent_layout.addWidget(result_container, stretch=1)

    def _connect_signals(self) -> None:
        """Connect UI signals to slots."""
        # Calculate button
        self.calc_button.clicked.connect(self._on_calculate)

        # Example button
        self.example_button.clicked.connect(self._show_examples_menu)

        # Button area
        self.clear_button.clicked.connect(self._on_clear)
        self.undo_button.clicked.connect(self._on_undo)
        self.redo_button.clicked.connect(self._on_redo)

        # Expression area
        self.copy_expr_button.clicked.connect(self._on_copy_expression)
        self.copy_latex_button.clicked.connect(self._on_copy_latex)

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts.

        Shortcuts:
            Ctrl+Return: Calculate expression
            Ctrl+L: Clear input field
            Escape: Clear input or close popup
        """
        # Ctrl+Return to calculate (works with both main Enter and numpad Enter)
        self.calc_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.input_field)
        self.calc_shortcut.activated.connect(self._on_calculate)

        # Ctrl+L to clear input
        self.clear_shortcut = QShortcut(QKeySequence("Ctrl+L"), self.input_field)
        self.clear_shortcut.activated.connect(self._on_clear)

        # Escape to clear input (only when input field is focused)
        self.esc_shortcut = QShortcut(QKeySequence("Escape"), self.input_field)
        self.esc_shortcut.activated.connect(self.input_field.clear)

    def _focus_input(self) -> None:
        """Focus the input field."""
        self.input_field.setFocus()

    def _setup_keyboard(self) -> None:
        """Set up the keyboard panel and ViewModel."""
        # Create ViewModel
        self._keyboard_viewmodel = KeyboardViewModel(parent=self)

        # Connect View -> ViewModel
        self.keyboard_panel.key_pressed.connect(self._keyboard_viewmodel.process_key)

        # Connect ViewModel -> View (input field)
        self._keyboard_viewmodel.text_inserted.connect(self._on_keyboard_text_inserted)

    def _on_keyboard_text_inserted(self, text: str, cursor_offset: int) -> None:
        """Handle text insertion from keyboard.

        Args:
            text: The text to insert.
            cursor_offset: Cursor offset after insertion (negative = move left).
        """
        cursor = self.input_field.textCursor()

        # Handle special keys
        if text == "\b":  # Backspace
            cursor.deletePreviousChar()
        elif text == "\x7f":  # Delete
            cursor.deleteChar()
        else:
            # Insert text
            cursor.insertText(text)

            # Apply cursor offset (smart positioning)
            if cursor_offset < 0:
                for _ in range(abs(cursor_offset)):
                    cursor.movePosition(QTextCursor.MoveOperation.Left)
                self.input_field.setTextCursor(cursor)

        self.input_field.setTextCursor(cursor)
        self.input_field.setFocus()

    def eventFilter(self, obj, event):
        """Filter events for input field.

        Handles smart mode switching:
        - In CODE mode: Press '=' when empty/whitespace -> switch to ASSIGN mode
        - In ASSIGN mode: Press Backspace when empty/whitespace -> switch to CODE mode

        Args:
            obj: The object that received the event.
            event: The event to filter.

        Returns:
            True if event was handled, False otherwise.
        """
        if obj == self.input_field and event.type() == event.Type.KeyPress:
            key_event = QKeyEvent(event)
            # Check if text is effectively empty (only whitespace)
            text = self.get_input_text()
            is_empty_or_whitespace = not text or text.isspace()

            # CODE mode + empty/whitespace + '=' -> switch to ASSIGN mode
            if (
                self._current_mode == InputMode.CODE
                and is_empty_or_whitespace
                and key_event.key() == Qt.Key.Key_Equal
            ):
                self._set_mode(InputMode.ASSIGN)
                return True  # Consume the event

            # ASSIGN mode + empty/whitespace + Backspace -> switch to CODE mode
            if (
                self._current_mode == InputMode.ASSIGN
                and is_empty_or_whitespace
                and key_event.key() == Qt.Key.Key_Backspace
            ):
                self._set_mode(InputMode.CODE)
                return True  # Consume the event

        return super().eventFilter(obj, event)

    def _on_mode_changed(self, item_id: str) -> None:
        """Handle mode selection change from SegmentedWidget.

        Args:
            item_id: The selected item ID ("code" or "assign").
        """
        if item_id == "code":
            self._set_mode(InputMode.CODE)
        elif item_id == "assign":
            self._set_mode(InputMode.ASSIGN)

    def _set_mode(self, mode: InputMode) -> None:
        """Set the input mode.

        Updates internal state and UI to reflect the new mode.
        Synchronizes with SegmentedWidget if needed.

        Args:
            mode: The input mode to set.
        """
        # Update internal state
        self._current_mode = mode

        # Update placeholder text
        if mode == InputMode.CODE:
            self.input_field.setPlaceholderText(self.tr("Enter expression..."))
        else:
            self.input_field.setPlaceholderText(
                self.tr("Enter assignment (e.g., x = 2 + 2)...")
            )

        # Sync SegmentedWidget if needed (avoid infinite loop)
        current_item = self.mode_selector.currentItem()
        target_item = "code" if mode == InputMode.CODE else "assign"
        if current_item != target_item:
            self.mode_selector.setCurrentItem(target_item)

        # Focus input after mode change
        self._focus_input()

    def _on_calculate(self) -> None:
        """Handle calculate button click."""
        expression = self.get_input_text().strip()
        if expression:
            self.calculate_requested.emit(expression, self._current_mode)
            self.select_all_input()
        # Focus input after calculation
        self._focus_input()

    def _on_clear(self) -> None:
        """Handle clear button click."""
        self.input_field.clear()
        self._focus_input()

    def _on_undo(self) -> None:
        """Handle undo button click."""
        self.input_field.undo()
        self._focus_input()

    def _on_redo(self) -> None:
        """Handle redo button click."""
        self.input_field.redo()
        self._focus_input()

    def _show_examples_menu(self) -> None:
        """Show the examples dropdown menu."""
        menu = RoundMenu(self.tr("Examples"), self)

        # Default examples
        examples = self._get_default_examples()

        for title, expr in examples:
            action = Action(
                text=f"{title}: {expr}",
                triggered=lambda checked, e=expr: self._on_example_selected(e),
            )
            menu.addAction(action)

        menu.exec(
            self.example_button.mapToGlobal(self.example_button.rect().bottomLeft())
        )

    def _on_example_selected(self, expression: str) -> None:
        """Handle example selection.

        Args:
            expression: The selected example expression.
        """
        self.set_input_text(expression)
        self.example_selected.emit(expression)
        # Focus input after selecting example
        self._focus_input()

    def _get_default_examples(self) -> List[Tuple[str, str]]:
        """Get default example expressions.

        Returns:
            List of (title, expression) tuples.
        """
        return [
            (self.tr("Derivative"), "diff(x**2, x)"),
            (self.tr("Integral"), "integrate(x**2, x)"),
            (self.tr("Limit"), "limit(sin(x)/x, x, 0)"),
            (self.tr("Solve"), "solve(x**2 - 4, x)"),
            (self.tr("Matrix"), "Matrix([[1, 2], [3, 4]])"),
        ]

    # Public API for ViewModel binding

    def get_input_text(self) -> str:
        """Get the current input text.

        Returns:
            The input field text.
        """
        return self.input_field.toPlainText()

    def set_input_text(self, text: str) -> None:
        """Set the input text.

        Args:
            text: The text to set.
        """
        self.input_field.setPlainText(text)

    def select_all_input(self) -> None:
        """Select all text in the input field."""
        self.input_field.selectAll()

    def set_expression(self, expression: str) -> None:
        """Set the expression label text.

        Args:
            expression: The expression to display.
        """
        self.expression_label.setText(expression)

    def show_latex_result(self, latex: str) -> None:
        """Show LaTeX result.

        Args:
            latex: The LaTeX expression to display.
        """
        self.latex_label.setText(latex)

    def get_plot_widget(self) -> MathPlotWidget:
        """Get the plot widget for plotting.

        Returns:
            The MathPlotWidget instance.
        """
        return self.plot_widget

    def clear_display(self) -> None:
        """Clear the expression label and result display."""
        self.expression_label.setText("")
        self.latex_label.setText("")
        self.plot_widget.canvas.axes.clear()
        self.plot_widget.canvas.draw()

    def show_info(self, title: str, content: str, duration: int = 2000) -> None:
        """Show an info message.

        Args:
            title: The message title.
            content: The message content.
            duration: Display duration in milliseconds. Defaults to 2000.
        """
        InfoBar.info(title=title, content=content, parent=self, duration=duration)

    def show_error(self, title: str, content: str, duration: int = 2000) -> None:
        """Show an error message.

        Args:
            title: The error title.
            content: The error content.
            duration: Display duration in milliseconds. Defaults to 2000.
        """
        InfoBar.error(title=title, content=content, parent=self, duration=duration)

    def plot_data(self, data_points) -> None:
        """Plot data points on the canvas.

        Args:
            data_points: PlotDataPoints containing x, y arrays and labels.
        """
        if data_points is None:
            return

        # Clear previous plot
        self.plot_widget.canvas.clear()

        # Plot the data using standard matplotlib API
        self.plot_widget.canvas.axes.plot(
            data_points.x, data_points.y, "b-", linewidth=2, label=data_points.label
        )

        # Set labels
        self.plot_widget.canvas.axes.set_xlabel(data_points.xlabel)
        self.plot_widget.canvas.axes.set_ylabel(data_points.ylabel)
        self.plot_widget.canvas.axes.set_title(data_points.title)

        # Grid and legend
        self.plot_widget.canvas.axes.grid(True, alpha=0.3)
        self.plot_widget.canvas.axes.legend()

        # Auto-scale and draw
        self.plot_widget.canvas.axes.autoscale_view()
        self.plot_widget.canvas.draw()

    def _on_copy_expression(self) -> None:
        """Copy current expression to clipboard."""
        from PySide6.QtWidgets import QApplication

        expression = self.get_input_text()
        QApplication.clipboard().setText(expression)
        self.expression_copied.emit(expression)

    def _on_copy_latex(self) -> None:
        """Copy current LaTeX to clipboard."""
        from PySide6.QtWidgets import QApplication

        latex = self.latex_label.text()
        QApplication.clipboard().setText(latex)
        self.latex_copied.emit(latex)

    def set_fonts(self, fonts: dict) -> None:
        """Set fonts for the interface components.

        Args:
            fonts: Dictionary containing font configurations.
        """
        if "large_monospace" in fonts:
            self.expression_label.setFont(fonts["large_monospace"])
