# coding: utf-8
"""Settings ViewModel for the Symplify application.

This module provides the ViewModel for the settings interface,
managing theme switching and application information.

Example:
    >>> from app.viewmodel import SettingsViewModel
    >>> vm = SettingsViewModel()
    >>> vm.set_theme(Theme.DARK)
"""

from typing import Optional

from PySide6.QtCore import QObject, Signal
from qfluentwidgets import Theme, qconfig, setTheme

from ..common.config import cfg


class SettingsViewModel(QObject):
    """ViewModel for the settings interface.

    Manages application settings including theme switching.

    Signals:
        theme_changed: Emitted when theme changes.
            Args:
                theme (Theme): The new theme.
        restart_required: Emitted when a restart is required.

    Attributes:
        current_theme: The current application theme.

    Example:
        >>> vm = SettingsViewModel()
        >>> vm.theme_changed.connect(on_theme_changed)
        >>> vm.set_theme(Theme.DARK)
    """

    theme_changed = Signal(object)  # Theme
    restart_required = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize the settings ViewModel.

        Args:
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._current_theme = cfg.themeMode.value

    @property
    def current_theme(self) -> Theme:
        """Get the current theme.

        Returns:
            The current Theme value.
        """
        return self._current_theme

    def get_theme(self) -> Theme:
        """Get the current theme (method version).

        Returns:
            The current Theme value.
        """
        return self._current_theme

    def set_theme(self, theme: Theme) -> None:
        """Set the application theme.

        Args:
            theme: The theme to set (LIGHT, DARK, or AUTO).

        Example:
            >>> vm.set_theme(Theme.DARK)
        """
        if theme != self._current_theme:
            self._current_theme = theme
            cfg.themeMode.value = theme
            # Sync to qconfig for QFluentWidgets internal consistency
            qconfig.themeMode.value = theme
            setTheme(theme)
            self.theme_changed.emit(theme)

    def get_app_info(self) -> dict:
        """Get application information.

        Returns:
            Dictionary containing app name, version, author, and year.

        Example:
            >>> info = vm.get_app_info()
            >>> print(info['name'])  # 'Symplify'
        """
        return {
            "name": cfg.APP_NAME,
            "version": cfg.VERSION,
            "author": cfg.AUTHOR,
            "year": cfg.YEAR,
        }

    def get_theme_options(self) -> list[tuple[Theme, str]]:
        """Get available theme options.

        Returns:
            List of (theme, display_name) tuples.
        """
        return [
            (Theme.LIGHT, "Light"),
            (Theme.DARK, "Dark"),
            (Theme.AUTO, "Use system setting"),
        ]
