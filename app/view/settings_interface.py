# coding: utf-8
"""Settings interface for the Symplify application.

This module provides the settings interface with theme switching
and application information, following MVVM architecture.

Example:
    >>> from PySide6.QtWidgets import QApplication
    >>> app = QApplication([])
    >>> from app.viewmodel import SettingsViewModel
    >>> vm = SettingsViewModel()
    >>> interface = SettingsInterface(viewmodel=vm)
    >>> interface.show()
"""

import sys
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QButtonGroup,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)
from qfluentwidgets import (
    ScrollArea,
    TitleLabel,
    SettingCardGroup,
    OptionsSettingCard,
    PrimaryPushSettingCard,
    ExpandLayout,
    FluentIcon,
    setTheme,
    setThemeColor,
    ExpandGroupSettingCard,
    RadioButton,
    ColorDialog,
)

from qfluentwidgets import qconfig

from ..common.config import cfg
from ..common.config_manager import ConfigManager
from ..viewmodel.settings_viewmodel import SettingsViewModel


class ThemeColorSettingCard(ExpandGroupSettingCard):
    """Theme color setting card with three modes: default, system, and custom.

    Provides radio buttons to select theme color mode and a color picker
    for custom color selection.

    Signals:
        themeColorChanged: Emitted when theme color changes.
            Args:
                color (QColor): The new theme color.
        themeColorModeChanged: Emitted when theme color mode changes.
            Args:
                mode (str): The new theme color mode ("default", "system", "custom").

    Example:
        >>> card = ThemeColorSettingCard(parent=settings_widget)
        >>> card.themeColorChanged.connect(on_color_changed)
    """

    themeColorChanged = Signal(QColor)
    themeColorModeChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the theme color setting card.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(
            FluentIcon.PALETTE,
            self.tr("Theme color"),
            self.tr("Change the theme color of your application"),
            parent=parent,
        )

        self._init_ui()
        self._connect_signals()
        self._load_config()

    def _init_ui(self) -> None:
        """Initialize the user interface."""
        # Choice label shown in header
        self.choice_label = QLabel(self)
        self.addWidget(self.choice_label)

        # Radio buttons widget
        self.radio_widget = QWidget(self.view)
        self.radio_layout = QVBoxLayout(self.radio_widget)
        self.radio_layout.setSpacing(19)
        self.radio_layout.setAlignment(Qt.AlignTop)
        self.radio_layout.setContentsMargins(48, 18, 0, 18)

        self.default_radio = RadioButton(self.tr("Default color"), self.radio_widget)
        self.system_radio = RadioButton(self.tr("System color"), self.radio_widget)
        self.custom_radio = RadioButton(self.tr("Custom color"), self.radio_widget)

        self.button_group = QButtonGroup(self)
        self.button_group.addButton(self.default_radio)
        self.button_group.addButton(self.system_radio)
        self.button_group.addButton(self.custom_radio)

        self.radio_layout.addWidget(self.default_radio)
        self.radio_layout.addWidget(self.system_radio)
        self.radio_layout.addWidget(self.custom_radio)

        # Custom color widget
        self.custom_color_widget = QWidget(self.view)
        self.custom_color_layout = QHBoxLayout(self.custom_color_widget)
        self.custom_color_layout.setContentsMargins(48, 18, 44, 18)

        self.custom_label = QLabel(self.tr("Custom color"), self.custom_color_widget)
        self.choose_color_button = QPushButton(
            self.tr("Choose color"), self.custom_color_widget
        )

        self.custom_color_layout.addWidget(self.custom_label, 0, Qt.AlignLeft)
        self.custom_color_layout.addWidget(self.choose_color_button, 0, Qt.AlignRight)

        # Add to view layout
        self.viewLayout.setSpacing(0)
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.addGroupWidget(self.radio_widget)
        self.addGroupWidget(self.custom_color_widget)

        # Set object names for styling
        self.choice_label.setObjectName("titleLabel")
        self.custom_label.setObjectName("titleLabel")
        self.choose_color_button.setObjectName("chooseColorButton")

    def _connect_signals(self) -> None:
        """Connect signals."""
        self.button_group.buttonClicked.connect(self._on_radio_button_clicked)
        self.choose_color_button.clicked.connect(self._on_choose_color_clicked)

    def _load_config(self) -> None:
        """Load configuration and set initial state."""
        mode = cfg.themeColorMode.value
        self._update_ui_for_mode(mode)

        if mode == "default":
            self.default_radio.setChecked(True)
        elif mode == "system":
            self.system_radio.setChecked(True)
        else:
            self.custom_radio.setChecked(True)

        self.choice_label.setText(self.button_group.checkedButton().text())
        self.choice_label.adjustSize()

    def _update_ui_for_mode(self, mode: str) -> None:
        """Update UI based on theme color mode.

        Args:
            mode: The theme color mode ("default", "system", "custom").
        """
        if mode == "custom":
            self.choose_color_button.setEnabled(True)
        else:
            self.choose_color_button.setEnabled(False)

    def _on_radio_button_clicked(self, button: RadioButton) -> None:
        """Handle radio button click.

        Args:
            button: The clicked radio button.
        """
        if button.text() == self.choice_label.text():
            return

        self.choice_label.setText(button.text())
        self.choice_label.adjustSize()

        if button is self.default_radio:
            self._set_default_mode()
        elif button is self.system_radio:
            self._set_system_mode()
        else:
            self._set_custom_mode()

    def _set_default_mode(self) -> None:
        """Set theme color to default mode."""
        # Only update mode, don't save color to ThemeColor config
        cfg.themeColorMode.value = "default"
        qconfig.save()
        self.choose_color_button.setEnabled(False)
        self.themeColorModeChanged.emit("default")
        # Emit the QFluentWidgets default color (#009faa, don't save)
        default_color = QColor(qconfig.themeColor.defaultValue)
        self.themeColorChanged.emit(default_color)

    def _set_system_mode(self) -> None:
        """Set theme color to system mode."""
        # Only update mode, don't save color to ThemeColor config
        cfg.themeColorMode.value = "system"
        qconfig.save()
        self.choose_color_button.setEnabled(False)
        self.themeColorModeChanged.emit("system")
        # Get system accent color if available (don't save)
        system_color = self._get_system_accent_color()
        if system_color.isValid():
            self.themeColorChanged.emit(system_color)

    def _set_custom_mode(self) -> None:
        """Set theme color to custom mode."""
        cfg.themeColorMode.value = "custom"
        qconfig.save()
        self.choose_color_button.setEnabled(True)
        self.themeColorModeChanged.emit("custom")
        # Emit the saved custom color from cfg.customThemeColor
        custom_color = QColor(cfg.customThemeColor.value)
        self.themeColorChanged.emit(custom_color)

    def _on_choose_color_clicked(self) -> None:
        """Handle choose color button click."""
        current_color = QColor(cfg.customThemeColor.value)
        dialog = ColorDialog(
            current_color, self.tr("Choose theme color"), self.window()
        )
        dialog.colorChanged.connect(self._on_custom_color_changed)
        dialog.exec()

    def _on_custom_color_changed(self, color: QColor) -> None:
        """Handle custom color change.

        Args:
            color: The new custom color.
        """
        # Save custom color to cfg.customThemeColor (persistent storage)
        # This is separate from qconfig.themeColor to avoid overwriting
        cfg.customThemeColor.value = color.name()
        qconfig.save()
        self.themeColorChanged.emit(color)

    def _get_system_accent_color(self) -> QColor:
        """Get system accent color.

        Returns:
            The system accent color, or invalid color if not available.
        """
        if sys.platform in ["win32", "darwin"]:
            try:
                from qframelesswindow.utils import getSystemAccentColor

                return getSystemAccentColor()
            except ImportError:
                pass
        return QColor()


class SettingsInterface(ScrollArea):
    """Settings interface for Symplify.

    Provides theme switching and application information display.
    Follows MVVM architecture with SettingsViewModel.

    Attributes:
        viewmodel: The Settings ViewModel.

    Example:
        >>> vm = SettingsViewModel()
        >>> interface = SettingsInterface(viewmodel=vm)
    """

    def __init__(
        self,
        viewmodel: Optional[SettingsViewModel] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the settings interface.

        Args:
            viewmodel: The Settings ViewModel. If None, creates a new one.
            parent: Optional parent widget.
        """
        super().__init__(parent=parent)

        # Create or use provided ViewModel
        self.viewmodel = viewmodel or SettingsViewModel(parent=self)

        # Initialize UI
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        """Initialize the user interface."""
        # Scroll widget and layout
        self.scroll_widget = QWidget()
        self.expand_layout = ExpandLayout(self.scroll_widget)

        # Settings label
        self.settings_label = TitleLabel(self.tr("Settings"), self)

        # Appearance group
        self.appearance_group = SettingCardGroup(
            self.tr("Appearance"), self.scroll_widget
        )
        self.theme_card = OptionsSettingCard(
            cfg.themeMode,
            FluentIcon.BRUSH,
            self.tr("Application theme"),
            self.tr("Change the appearance of your application"),
            texts=[self.tr("Light"), self.tr("Dark"), self.tr("Use system setting")],
            parent=self.appearance_group,
        )
        self.theme_color_card = ThemeColorSettingCard(self.appearance_group)

        # About group
        self.about_group = SettingCardGroup(self.tr("About"), self.scroll_widget)
        self._setup_about_card()

        # Setup layout
        self._setup_layout()
        self._setup_style()

    def _setup_about_card(self) -> None:
        """Setup the about card with app info."""
        info = self.viewmodel.get_app_info()
        self.about_card = PrimaryPushSettingCard(
            self.tr("Check update"),
            FluentIcon.INFO,
            self.tr("About"),
            f"© {self.tr('Copyright')} {info['year']}, {info['author']}. "
            + f"{self.tr('Version')} {info['version']}",
            self.about_group,
        )

    def _setup_layout(self) -> None:
        """Setup the widget layout."""
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scroll_widget)
        self.setWidgetResizable(True)

        # Add cards to groups
        self.appearance_group.addSettingCard(self.theme_card)
        self.appearance_group.addSettingCard(self.theme_color_card)
        self.about_group.addSettingCard(self.about_card)

        # Add groups to layout
        self.expand_layout.setSpacing(28)
        self.expand_layout.setContentsMargins(36, 10, 36, 0)
        self.expand_layout.addWidget(self.appearance_group)
        self.expand_layout.addWidget(self.about_group)

        # Position label
        self.settings_label.move(36, 30)

    def _setup_style(self) -> None:
        """Setup widget styles"""
        self.enableTransparentBackground()

    def _connect_signals(self) -> None:
        """Connect signals."""
        # Theme changed from qconfig (QFluentWidgets global config)
        qconfig.themeChanged.connect(setTheme)
        # Theme color changed from theme color card
        self.theme_color_card.themeColorChanged.connect(
            lambda color: setThemeColor(color, save=False)
        )
