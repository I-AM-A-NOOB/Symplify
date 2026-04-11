# coding: utf-8
"""UI utility functions for the Symplify application.

This module provides helper functions for common UI operations,
such as showing info bars and message dialogs.

Example:
    >>> from app.common.ui_utils import InfoBarHelper
    >>> InfoBarHelper.show_error(self, "Error", "Something went wrong")
    >>> InfoBarHelper.show_info(self, "Success", "Operation completed")
"""
from typing import Optional

from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition


class InfoBarHelper:
    """Helper class for showing InfoBar messages.

    Provides static methods for showing error, info, success, and warning
    messages using QFluentWidgets' InfoBar component.

    Example:
        >>> InfoBarHelper.show_error(parent, "Error", "Invalid input")
        >>> InfoBarHelper.show_success(parent, "Saved", "File saved successfully")
    """

    @staticmethod
    def show_error(
        parent: QWidget,
        title: str,
        content: str,
        duration: int = 3000,
        position: InfoBarPosition = InfoBarPosition.TOP,
    ) -> None:
        """Show an error message.

        Args:
            parent: The parent widget.
            title: The error title.
            content: The error content.
            duration: Display duration in milliseconds. Defaults to 3000.
            position: Position on screen. Defaults to TOP.
        """
        InfoBar.error(title=title, content=content, parent=parent, position=position, duration=duration)

    @staticmethod
    def show_info(
        parent: QWidget,
        title: str,
        content: str,
        duration: int = 2000,
        position: InfoBarPosition = InfoBarPosition.TOP,
    ) -> None:
        """Show an info message.

        Args:
            parent: The parent widget.
            title: The info title.
            content: The info content.
            duration: Display duration in milliseconds. Defaults to 2000.
            position: Position on screen. Defaults to TOP.
        """
        InfoBar.info(title=title, content=content, parent=parent, position=position, duration=duration)

    @staticmethod
    def show_success(
        parent: QWidget,
        title: str,
        content: str,
        duration: int = 2000,
        position: InfoBarPosition = InfoBarPosition.TOP,
    ) -> None:
        """Show a success message.

        Args:
            parent: The parent widget.
            title: The success title.
            content: The success content.
            duration: Display duration in milliseconds. Defaults to 2000.
            position: Position on screen. Defaults to TOP.
        """
        InfoBar.success(title=title, content=content, parent=parent, position=position, duration=duration)

    @staticmethod
    def show_warning(
        parent: QWidget,
        title: str,
        content: str,
        duration: int = 3000,
        position: InfoBarPosition = InfoBarPosition.TOP,
    ) -> None:
        """Show a warning message.

        Args:
            parent: The parent widget.
            title: The warning title.
            content: The warning content.
            duration: Display duration in milliseconds. Defaults to 3000.
            position: Position on screen. Defaults to TOP.
        """
        InfoBar.warning(title=title, content=content, parent=parent, position=position, duration=duration)
