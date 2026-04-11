# coding: utf-8
"""Keyboard ViewModel for the Symplify application.

This module provides the ViewModel for the keyboard panel,
handling input processing and business logic.

Example:
    >>> from app.viewmodel import KeyboardViewModel
    >>> vm = KeyboardViewModel()
    >>> vm.text_inserted.connect(handle_text_insert)
    >>> vm.process_key("sin(")
"""
from typing import Optional, Tuple

from PySide6.QtCore import QObject, Signal


class KeyboardViewModel(QObject):
    """ViewModel for keyboard input processing.

    Handles keyboard button clicks and processes text insertion,
    including smart cursor positioning for functions.

    Signals:
        text_inserted: Emitted when text should be inserted.
            Args:
                text (str): The text to insert.
                cursor_offset (int): Cursor offset after insertion (negative = move left).

    Example:
        >>> vm = KeyboardViewModel()
        >>> vm.text_inserted.connect(lambda text, offset: print(f"Insert '{text}', move {offset}"))
        >>> vm.process_key("sin(")
        Insert 'sin(', move -1
    """

    text_inserted = Signal(str, int)  # text, cursor_offset

    def process_key(self, key: str) -> None:
        """Process a keyboard key press.

        Args:
            key: The key label/text to process.

        Example:
            >>> vm.process_key("7")  # Normal key
            >>> vm.process_key("sin(")  # Function with smart cursor
            >>> vm.process_key("\\b")  # Backspace
        """
        if not key:
            return

        # Handle special keys
        if key == "\b":  # Backspace
            self.text_inserted.emit("\b", 0)
            return

        if key == "\x7f":  # Delete
            self.text_inserted.emit("\x7f", 0)
            return

        # Calculate cursor offset for smart positioning
        cursor_offset = 0
        if "(" in key and ")" not in key:
            # Move cursor inside parentheses
            cursor_offset = -(len(key) - key.find("(") - 1)

        self.text_inserted.emit(key, cursor_offset)
