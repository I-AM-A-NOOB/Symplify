# coding: utf-8
"""Keyboard panel component for calculator input.

This module provides a keyboard panel for the calculator interface,
supporting multiple keyboard layouts loaded from YAML configuration.
This is a pure View component - all logic is handled by KeyboardViewModel.

Example:
    >>> from app.components import KeyboardPanel
    >>> from app.viewmodel import KeyboardViewModel
    >>> keyboard = KeyboardPanel()
    >>> viewmodel = KeyboardViewModel()
    >>> keyboard.key_pressed.connect(viewmodel.process_key)
"""

from typing import Any, Dict, List, Optional

import yaml
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CardWidget,
    PushButton,
    SegmentedWidget,
    SingleDirectionScrollArea,
)


def load_keyboard_config() -> Dict[str, Any]:
    """Load keyboard configuration from YAML file.

    Returns:
        Dictionary containing keyboard layout configurations.

    Example:
        >>> config = load_keyboard_config()
        >>> print(config.keys())
        dict_keys(['basic', 'functions', 'symbols', ...])
    """
    config_path = __file__.replace("keyboard_panel.py", "keyboard_config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class KeyboardPanel(CardWidget):
    """Soft keyboard panel for calculator input (View only).

    Provides a tabbed keyboard interface with grid layouts.
    This is a pure View component - it only handles UI and emits signals.
    All business logic is handled by KeyboardViewModel.

    Signals:
        key_pressed: Emitted when a keyboard button is clicked.
            Args:
                key (str): The key text/label.

    Example:
        >>> keyboard = KeyboardPanel()
        >>> keyboard.key_pressed.connect(viewmodel.process_key)
        >>> keyboard.apply_settings(QFont("Consolas", 12))
    """

    key_pressed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the keyboard panel.

        Args:
            parent: The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self._keyboard_font: Optional[QFont] = None
        self._config = load_keyboard_config()

        self._setup_ui()
        self._create_keyboards()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Scroll area for tab bar (collapses when space is insufficient)
        self._tab_scroll = SingleDirectionScrollArea(orient=Qt.Orientation.Horizontal)
        self._tab_scroll.setWidgetResizable(True)
        self._tab_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._tab_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._tab_scroll.setStyleSheet(
            "QScrollArea{background: transparent; border: none}"
        )
        self._tab_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        # Tab bar for switching keyboard layouts
        self._tab_bar = SegmentedWidget()
        self._tab_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self._tab_scroll.setWidget(self._tab_bar)
        layout.addWidget(self._tab_scroll)

        # Stacked widget for keyboard pages
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

    def _create_keyboards(self) -> None:
        """Create all keyboard layouts from configuration."""
        for route_key, config in self._config.items():
            page = self._create_grid_page(config.get("grid", []))
            self._stack.addWidget(page)

            # Add tab with widget reference in closure
            # Use default argument to capture page, ignore the checked argument from signal
            self._tab_bar.addItem(
                routeKey=route_key,
                text=config["title"],
                onClick=lambda checked, w=page: self._stack.setCurrentWidget(w),
            )

        # Select first tab
        if self._config:
            first_key = list(self._config.keys())[0]
            self._tab_bar.setCurrentItem(first_key)

    def _create_grid_page(self, grid: List[List[str]]) -> QWidget:
        """Create a grid layout keyboard page.

        Args:
            grid: 2D list of button labels.

        Returns:
            QWidget containing the keyboard grid.
        """
        page = QWidget()
        layout = QGridLayout(page)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        for row_idx, row in enumerate(grid):
            for col_idx, label in enumerate(row):
                if not label:
                    continue

                btn = self._create_button(label)
                layout.addWidget(btn, row_idx, col_idx)

        return page

    def _create_button(self, label: str) -> PushButton:
        """Create a keyboard button.

        Args:
            label: The button label/text.

        Returns:
            Configured PushButton.
        """
        btn = PushButton(label)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        btn.setMinimumHeight(36)

        if self._keyboard_font:
            btn.setFont(self._keyboard_font)

        # Emit signal instead of direct manipulation
        btn.clicked.connect(lambda checked, text=label: self.key_pressed.emit(text))

        return btn

    def apply_settings(self, font: Optional[QFont] = None) -> None:
        """Apply font settings to all keyboard buttons.

        Args:
            font: The font to apply. If None, uses default font.

        Example:
            >>> keyboard.apply_settings(QFont("Consolas", 12))
        """
        if font:
            self._keyboard_font = font

            # Update all buttons
            for i in range(self._stack.count()):
                page = self._stack.widget(i)
                for btn in page.findChildren(PushButton):
                    btn.setFont(font)
