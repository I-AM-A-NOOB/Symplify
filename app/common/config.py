# coding: utf-8
"""Application configuration for Symplify.

This module provides application-wide configuration management
using QFluentWidgets' QConfig system.

Example:
    >>> from app.common.config import cfg
    >>> cfg.themeMode.value = Theme.DARK
"""

import os
import sys
from pathlib import Path

from qfluentwidgets import (
    qconfig,
    QConfig,
    OptionsConfigItem,
    OptionsValidator,
    Theme,
    EnumSerializer,
    ColorConfigItem,
)


def _get_portable_config_dir() -> Path | None:
    """Check if portable mode is enabled.

    Portable mode is enabled when a `.config` folder exists in the
    application root directory (where main.py is located).

    Returns:
        Path to the portable config directory if enabled, None otherwise.

    Example:
        >>> portable_dir = _get_portable_config_dir()
        >>> if portable_dir:
        ...     print(f"Running in portable mode: {portable_dir}")
    """
    # Get the directory containing this file (app/common/)
    # Then go up to the project root
    current_file = Path(__file__).resolve()
    app_dir = current_file.parent.parent  # app/
    project_root = app_dir.parent  # project root (where main.py is)

    portable_dir = project_root / ".config"

    if portable_dir.exists() and portable_dir.is_dir():
        return portable_dir

    return None


def get_config_dir() -> Path:
    """Get the configuration directory.

    Returns the configuration directory in the following priority:
    1. Portable mode: <project_root>/.config/ (if .config folder exists)
    2. Platform-specific:
       - Windows: %LOCALAPPDATA%/Symplify/
       - macOS: ~/Library/Application Support/Symplify/
       - Linux: ~/.config/Symplify/

    The directory is created automatically if it doesn't exist.

    Returns:
        Path: The configuration directory path.

    Example:
        >>> config_dir = get_config_dir()
        >>> print(config_dir)
        WindowsPath('C:/Users/Username/AppData/Local/Symplify')
        >>> # Get specific config file
        >>> config_file = config_dir / "config.json"
        >>> history_file = config_dir / "history.json"
    """
    # Check for portable mode first
    portable_dir = _get_portable_config_dir()
    if portable_dir:
        # Portable mode: use <project_root>/.config/
        config_dir = portable_dir
    elif sys.platform == "win32":
        # Windows: %LOCALAPPDATA%/Symplify/
        base_path = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        config_dir = Path(base_path) / "Symplify"
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/Symplify/
        config_dir = Path.home() / "Library" / "Application Support" / "Symplify"
    else:
        # Linux: ~/.config/Symplify/
        config_dir = Path.home() / ".config" / "Symplify"

    # Ensure directory exists
    config_dir.mkdir(parents=True, exist_ok=True)

    return config_dir


def get_config_path(filename: str = "config.json") -> str:
    """Get the full path for a specific configuration file.

    Args:
        filename: The configuration file name. Defaults to "config.json".

    Returns:
        str: The full path to the configuration file.

    Example:
        >>> # Get main config file
        >>> path = get_config_path()
        >>> print(path)
        'C:/Users/Username/AppData/Local/Symplify/config.json'
        >>> # Get history file
        >>> history_path = get_config_path("history.json")
        >>> print(history_path)
        'C:/Users/Username/AppData/Local/Symplify/history.json'
    """
    return str(get_config_dir() / filename)


class Config(QConfig):
    """Configuration for Symplify application.

    Attributes:
        themeMode: Theme mode (Light/Dark/Auto).
        themeColorMode: Theme color mode (default/system/custom).
        customThemeColor: Custom theme color (persistent storage).

    Note:
        Default theme color is inherited from QFluentWidgets (#009faa).
    """

    # Application info (not config items)
    APP_NAME = "Symplify"
    VERSION = "1.0.0"
    AUTHOR = "Your Name"
    YEAR = "2024"

    # Theme mode - stored in config file for persistence
    themeMode = OptionsConfigItem(
        "Appearance",
        "ThemeMode",
        Theme.AUTO,
        OptionsValidator([Theme.LIGHT, Theme.DARK, Theme.AUTO]),
        EnumSerializer(Theme),
    )

    # Theme color settings
    themeColorMode = OptionsConfigItem(
        "Appearance",
        "ThemeColorMode",
        "default",
        OptionsValidator(["default", "system", "custom"]),
    )
    # User's custom theme color (persistent storage)
    # This is separate from qconfig.themeColor which represents the current display color
    customThemeColor = ColorConfigItem(
        "Appearance",
        "CustomThemeColor",
        "#009faa",
    )


# Global config instance
cfg = Config()
config_path = get_config_path()
qconfig.load(config_path, cfg)
