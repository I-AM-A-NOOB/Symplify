# coding: utf-8
"""Log interface for the Symplify application.

This module provides a simple log display interface without a ViewModel,
directly displaying log content passed to it.

Example:
    >>> from app.view.log_interface import LogInterface
    >>> log_interface = LogInterface()
    >>> log_interface.set_log_content("Calculation log...")
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from qfluentwidgets import (
    ScrollArea,
    PlainTextEdit,
    PushButton,
    SubtitleLabel,
    FluentIcon,
    ToolTipFilter,
    ToolTipPosition,
)


class LogInterface(ScrollArea):
    """Log display interface.
    
    A simple view-only interface for displaying calculation logs.
    No ViewModel needed - just displays content set on it.
    
    Attributes:
        text_edit: The text edit widget for displaying logs.
        
    Example:
        >>> interface = LogInterface()
        >>> interface.set_log_content("x = 2\\ny = 3\\nresult = 5")
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the log interface.
        
        Args:
            parent: The parent widget. Defaults to None.
        """
        super().__init__(parent)
        
        self._setup_ui()
        self._setup_style()
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create container widget
        self.container = QWidget(self)
        self.setWidget(self.container)
        self.setWidgetResizable(True)
        
        # Main layout
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Title
        title_label = SubtitleLabel(self.tr("Calculation Log"), self)
        layout.addWidget(title_label)
        
        # Text edit for log content
        self.text_edit = PlainTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText(self.tr("No calculations yet..."))
        layout.addWidget(self.text_edit)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Clear button
        self.clear_button = PushButton(self.tr("Clear"), self)
        self.clear_button.setIcon(FluentIcon.DELETE)
        self.clear_button.setToolTip(self.tr("Clear log content"))
        self.clear_button.installEventFilter(
            ToolTipFilter(self.clear_button, 300, ToolTipPosition.TOP)
        )
        self.clear_button.clicked.connect(self.clear_log)
        button_layout.addWidget(self.clear_button)
        
        # Copy button
        self.copy_button = PushButton(self.tr("Copy"), self)
        self.copy_button.setIcon(FluentIcon.COPY)
        self.copy_button.setToolTip(self.tr("Copy log to clipboard"))
        self.copy_button.installEventFilter(
            ToolTipFilter(self.copy_button, 300, ToolTipPosition.TOP)
        )
        self.copy_button.clicked.connect(self._copy_log)
        button_layout.addWidget(self.copy_button)
        
        layout.addLayout(button_layout)
    
    def _setup_style(self) -> None:
        """Apply styling to the interface."""
        # Enable transparent background
        self.setStyleSheet("background: transparent; border: none;")
        self.container.setStyleSheet("background: transparent;")
    
    def set_log_content(self, content: str) -> None:
        """Set the log content to display.
        
        Args:
            content: The log content string.
        """
        self.text_edit.setPlainText(content)
        # Scroll to bottom
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_log(self) -> None:
        """Clear the log content."""
        self.text_edit.clear()
    
    def _copy_log(self) -> None:
        """Copy log content to clipboard."""
        from PySide6.QtWidgets import QApplication
        
        content = self.text_edit.toPlainText()
        if content:
            QApplication.clipboard().setText(content)
    
    def append_log(self, message: str) -> None:
        """Append a message to the log.
        
        Args:
            message: The message to append.
        """
        current = self.text_edit.toPlainText()
        if current:
            new_content = current + "\n" + message
        else:
            new_content = message
        self.set_log_content(new_content)
