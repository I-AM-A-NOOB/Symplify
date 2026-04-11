# coding: utf-8
"""Configuration manager for centralized config loading and application.

This module provides ConfigManager, a centralized way to load and apply
all application configurations at startup.

Example:
    >>> from app.common.config_manager import ConfigManager
    >>> ConfigManager.load()  # Load and apply all configs
"""

import sys

from PySide6.QtGui import QColor, QPalette
from qfluentwidgets import qconfig, setTheme, setThemeColor

from .config import cfg


class ConfigManager:
    """Manager for application configuration.

    Handles loading and applying all configuration settings
    in a centralized manner. Call load() at application startup.

    Example:
        >>> ConfigManager.load()  # Apply all configurations
    """

    @staticmethod
    def load() -> None:
        """Load and apply all configurations.

        This method should be called once at application startup,
        after QApplication is created but before MainWindow is shown.
        """
        # Apply theme configuration
        ConfigManager._apply_theme()
        # Apply theme color configuration
        ConfigManager._apply_theme_color()

        # Future: Apply other configurations here
        # ConfigManager._apply_window_settings()
        # ConfigManager._apply_font_settings()
        # ConfigManager._apply_language_settings()

    @staticmethod
    def _apply_theme() -> None:
        """Apply theme configuration.

        Applies the saved theme (Light/Dark/Auto) to the application.
        Auto theme is resolved based on system settings.

        Note:
            cfg.themeMode is now a proper ConfigItem (not a proxy to qconfig.themeMode),
            so changes are automatically saved to the config file.
            We also sync it to qconfig.themeMode for QFluentWidgets internal use.
        """
        theme = cfg.themeMode.value
        setTheme(theme)
        # Sync to qconfig for QFluentWidgets internal consistency
        qconfig.themeMode.value = theme

    @staticmethod
    def _apply_theme_color() -> None:
        """Apply theme color configuration.

        Applies the saved theme color based on ThemeColorMode:
        - "default": Use QFluentWidgets default color (#009faa)
        - "system": Use system accent color (Windows/macOS only)
        - "custom": Use the saved custom color
        """
        mode = cfg.themeColorMode.value

        if mode == "default":
            # Use QFluentWidgets default color (#009faa)
            default_color = QColor(qconfig.themeColor.defaultValue)
            setThemeColor(default_color, save=False)
        elif mode == "system":
            # Use system accent color
            system_color = ConfigManager._get_system_accent_color()
            if system_color.isValid():
                setThemeColor(system_color, save=False)
            else:
                # Fallback to default if system color not available
                default_color = QColor(qconfig.themeColor.defaultValue)
                setThemeColor(default_color, save=False)
        else:  # "custom"
            # Use saved custom color from cfg.customThemeColor
            # This is separate from qconfig.themeColor to avoid overwriting
            custom_color = QColor(cfg.customThemeColor.value)
            setThemeColor(custom_color, save=False)

    @staticmethod
    def _get_system_accent_color() -> QColor:
        """Get system accent color.

        Returns:
            The system accent color, or invalid color if not available.

        Note:
            - Windows/macOS: Uses qframelesswindow.utils.getSystemAccentColor
            - Linux: Falls back to QPalette.Highlight color from application palette
        """
        if sys.platform in ["win32", "darwin"]:
            try:
                from qframelesswindow.utils import getSystemAccentColor

                return getSystemAccentColor()
            except ImportError:
                pass
        else:
            # Linux fallback: Use QPalette.Highlight as system accent color
            # QPalette.Highlight typically maps to the system's selection/highlight color
            # which is often themed to match the system accent color on Linux DEs
            palette = QPalette()
            return palette.color(palette.ColorGroup.Active, palette.ColorRole.Highlight)

        return QColor()

    # Future extension points for additional configurations:

    # @staticmethod
    # def _apply_window_settings() -> None:
    #     """Apply window size and position settings."""
    #     pass

    # @staticmethod
    # def _apply_font_settings() -> None:
    #     """Apply font and DPI settings."""
    #     pass

    # @staticmethod
    # def _apply_language_settings() -> None:
    #     """Apply language and locale settings."""
    #     pass
