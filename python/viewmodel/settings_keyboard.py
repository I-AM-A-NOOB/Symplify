"""Keyboard settings: the custom layout folder, its files and its errors.

Methods only. The ``Property`` declarations and ``Signal`` objects live on
``SettingsViewModel`` (the QObject subclass), so shiboken registers them; this
module is mixed in and refers to them through ``self``. ``_set_keyboard_layout``
emits ``keyboardChanged`` and the catch-all ``changed``.
"""

from pathlib import Path

from PySide6.QtCore import QUrl, Slot
from PySide6.QtGui import QDesktopServices

from ..keyboard_config import keyboard_dir, keyboard_files, new_keyboard_file


class KeyboardSettings:
    """Applies and persists the custom keyboard selection."""

    def _keyboard_folder(self) -> Path:
        return keyboard_dir(self._store.path.parent)

    def _keyboard_layout_path(self) -> Path | None:
        name = self._get_keyboard_layout()
        return self._keyboard_folder() / name if name else None

    def _get_keyboard_folder(self) -> str:
        return str(self._keyboard_folder())

    def _get_keyboard_layouts(self) -> list:
        return [path.name for path in keyboard_files(self._keyboard_folder())]

    def _get_keyboard_layout(self) -> str:
        return self._store.get("workspace.keyboard_layout")

    def _set_keyboard_layout(self, name: str) -> None:
        name = name.strip() if isinstance(name, str) else ""
        if name and name not in self._get_keyboard_layouts():
            name = ""
        self._store.set("workspace.keyboard_layout", name)
        self.keyboardChanged.emit()
        self.changed.emit()

    def _get_keyboard_error(self) -> str:
        return self._keyboard_error

    @Slot(result=str)
    def suggestKeyboardName(self) -> str:
        """The next free ``myboard-N`` name, counted like a new variable."""
        taken = {
            Path(name).stem.casefold()
            for name in self._get_keyboard_layouts()
        }
        counter = 1
        while f"myboard-{counter}".casefold() in taken:
            counter += 1
        return f"myboard-{counter}"

    @Slot()
    def refreshKeyboardLayouts(self) -> None:
        """Re-list the folder; reset a selection whose file has disappeared."""
        names = self._get_keyboard_layouts()
        self.keyboardLayoutsChanged.emit()
        if self._get_keyboard_layout() not in [""] + names:
            self._set_keyboard_layout("")

    @Slot(str, str, result=str)
    def newKeyboardLayout(self, name: str, source: str) -> str:
        """Copy a layout into the settings folder under ``name`` and select it.

        ``source`` is ``""`` for the shipped layout or a filename currently in
        the keyboard folder. Returns the created filename, or ``""`` after
        putting the reason in ``keyboardError``.
        """
        source_path: Path | None = None
        if source:
            if source not in self._get_keyboard_layouts():
                self._keyboard_error = f"{source} is not in the keyboard folder"
                self.keyboardErrorChanged.emit()
                return ""
            source_path = self._keyboard_folder() / source
        try:
            path = new_keyboard_file(
                self._keyboard_folder(), source=source_path, name=name
            )
        except (OSError, ValueError) as exc:
            self._keyboard_error = str(exc)
            self.keyboardErrorChanged.emit()
            return ""
        self._keyboard_error = ""
        self.keyboardErrorChanged.emit()
        self.keyboardLayoutsChanged.emit()
        self._set_keyboard_layout(path.name)
        return path.name

    @Slot()
    def clearKeyboardError(self) -> None:
        if not self._keyboard_error:
            return
        self._keyboard_error = ""
        self.keyboardErrorChanged.emit()

    @Slot()
    def openKeyboardFolder(self) -> None:
        """Open the settings-folder keyboards directory, creating it if needed."""
        folder = self._keyboard_folder()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._keyboard_error = str(exc)
            self.keyboardErrorChanged.emit()
            return
        if self._keyboard_error:
            self._keyboard_error = ""
            self.keyboardErrorChanged.emit()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
