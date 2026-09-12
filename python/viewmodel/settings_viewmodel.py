# coding: utf-8
"""Settings viewmodel: the settings store on one side, RinUI and QML on the other.

The store (``python/settings.py``) is the single source of truth; RinUI's own
persistence is taken over at import time by ``python/rinui_bootstrap.py``. This
viewmodel is the **only** writer of settings: every setter stores the value and
applies it live, so the file and the running UI cannot disagree.

Appearance is applied through RinUI's ``ThemeManager`` QObject (the QML ``Theme``
singleton is a thin wrapper around it), which is why the window's theme manager is
passed in rather than reached for globally. Rendering settings are applied by
``MainViewModel``, which owns the viewmodels that render.
"""

from typing import Optional, Tuple

from PySide6.QtCore import Property, QObject, QPoint, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from ..settings import DEFAULTS, SettingsStore


class SettingsViewModel(QObject):
    """Applies and persists the user settings.

    Signals:
        changed: Any setting changed, including the config-write status.
        latexSizeChanged: The result font size changed (renderers must re-render).
    """

    changed = Signal()
    latexSizeChanged = Signal()
    accentChanged = Signal()

    def __init__(
        self,
        store: SettingsStore,
        theme_manager: Optional[QObject] = None,
        parent: Optional[QObject] = None,
    ):
        """Initialize the settings viewmodel.

        Args:
            store: The loaded settings store.
            theme_manager: RinUI's ``ThemeManager``; when None (tests) appearance
                is still persisted but not applied to the running UI.
        """
        super().__init__(parent)
        self._store = store
        self._theme_manager = theme_manager
        self._window: Optional[QObject] = None
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.setInterval(500)
        self._geometry_timer.timeout.connect(self._save_geometry)
        # Appearance is NOT re-applied here: the bootstrap already injected it into
        # RinUI's config before the window existed, and applying a backdrop needs a
        # window handle (RinUI warns and refuses without one). _apply_appearance is
        # for after-the-fact changes, i.e. restore-defaults.

    # --- appearance -------------------------------------------------------

    def _apply_appearance(self) -> None:
        """Push the stored appearance into RinUI (no-op without a theme manager).

        The accent colour is *not* applied here: RinUI's own
        ``Theme.setThemeColor`` also sets ``Utils.primaryColor``, which is what
        actually re-colours the UI, so it has to run on the QML side (see the
        ``accentChanged`` handler in SettingsPage.qml). This method is for theme
        and backdrop, which apply fine through the Python slots.
        """
        if self._theme_manager is None:
            return
        self._theme_manager.toggle_theme(self._get_theme())
        self._theme_manager.apply_backdrop_effect(self._get_backdrop())

    def _get_theme(self) -> str:
        return self._store.get("appearance.theme")

    def _set_theme(self, theme: str) -> None:
        theme = self._store.set("appearance.theme", theme)
        if self._theme_manager is not None and self._theme_manager.get_theme_name() != theme:
            self._theme_manager.toggle_theme(theme)
        self.changed.emit()

    def _get_backdrop(self) -> str:
        return self._store.get("appearance.backdrop")

    def _set_backdrop(self, backdrop: str) -> None:
        backdrop = self._store.set("appearance.backdrop", backdrop)
        if self._theme_manager is not None:
            self._theme_manager.apply_backdrop_effect(backdrop)
        self.changed.emit()

    def _get_accent(self) -> str:
        return self._store.get("appearance.accent")

    def _set_accent(self, accent: str) -> None:
        """Persist the accent colour and ask the QML side to apply it.

        RinUI's Python slot only persists the value; the visible change comes from
        ``Utils.primaryColor``, which its QML ``Theme.setThemeColor`` sets too.
        """
        self._store.set("appearance.accent", accent)
        self.accentChanged.emit()
        self.changed.emit()

    # --- rendering --------------------------------------------------------

    def _get_latex_size(self) -> int:
        return int(self._store.get("rendering.latex_size"))

    def _set_latex_size(self, size: int) -> None:
        self._store.set("rendering.latex_size", size)
        self.latexSizeChanged.emit()
        self.changed.emit()

    # --- window geometry --------------------------------------------------

    def _get_remember_window(self) -> bool:
        return bool(self._store.get("window.remember"))

    def _set_remember_window(self, remember: bool) -> None:
        self._store.set("window.remember", remember)
        if remember:
            self._save_geometry()      # start remembering from the current geometry
        self.changed.emit()

    @Slot(QObject)
    def attachWindow(self, window: QObject) -> None:
        """Restore and then remember the window geometry (called by MainWindow.qml).

        Position is only restored when the saved point still falls on a screen —
        otherwise a window remembered on a monitor that is now gone would open
        off-screen.
        """
        self._window = window
        if not self._get_remember_window():
            return
        self._restore_geometry()
        for signal_name in ("widthChanged", "heightChanged", "xChanged", "yChanged"):
            getattr(window, signal_name).connect(self._on_geometry_changed)
        window.closing.connect(self._save_geometry)

    def _on_geometry_changed(self, *_) -> None:
        """Restart the debounce (window signals carry the new value as an int)."""
        self._geometry_timer.start()

    def _restore_geometry(self) -> None:
        """Move the window to its remembered position.

        The *size* is not set here on purpose: it comes from
        ``MainWindow.qml``'s ``width``/``height`` bindings (see
        :attr:`startupWidth`). Resizing the window at this point — while it is
        still being created — and then maximizing it leaves the presentation
        stale on Windows: the window fills the screen and Qt reports the right
        sizes, but what is drawn stays in the old rectangle with a white border,
        and later resizes do not repair it. Verified against RinUI 0.4.4.1.
        """
        window = self._window
        if window is None:
            return
        x, y = self._store.get("window.x"), self._store.get("window.y")
        if x is not None and y is not None and self._is_on_a_screen(int(x), int(y)):
            window.setProperty("x", int(x))
            window.setProperty("y", int(y))
        if self._store.get("window.maximized"):
            # Maximizing before the window is shown has the same stale-surface
            # effect, so the state is applied once the window is actually shown.
            # MainWindow.qml declares `visible: true`, so at this point it usually
            # already is — hence the timer fallback rather than only the signal.
            if window.property("visible"):
                QTimer.singleShot(0, self._apply_maximized_once)
            else:
                window.visibleChanged.connect(self._apply_maximized_once)

    def _apply_maximized_once(self, *_) -> None:
        """Maximize after the window is shown, then stop listening."""
        window = self._window
        if window is None or not window.property("visible"):
            return
        try:
            window.visibleChanged.disconnect(self._apply_maximized_once)
        except (RuntimeError, TypeError):
            pass
        window.showMaximized()

    def _startup_size(self) -> Tuple[int, int]:
        """The size the window should be *created* with.

        Never larger than the screen the window will open on — a geometry saved
        on a bigger monitor must not produce a window that cannot be reached.
        """
        width = int(self._store.get("window.width"))
        height = int(self._store.get("window.height"))
        app = QGuiApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width())
            height = min(height, available.height())
        return width, height

    def _get_startup_width(self) -> int:
        if not self._get_remember_window():
            return int(DEFAULTS["window"]["width"])
        return self._startup_size()[0]

    def _get_startup_height(self) -> int:
        if not self._get_remember_window():
            return int(DEFAULTS["window"]["height"])
        return self._startup_size()[1]


    def _is_on_a_screen(self, x: int, y: int) -> bool:
        """Whether the point is still inside a connected screen's work area."""
        screens = QGuiApplication.screens()
        if not screens:
            return True                      # headless (tests): do not block
        point = QPoint(x, y)
        return any(screen.availableGeometry().contains(point) for screen in screens)

    def _save_geometry(self, *_) -> None:
        """Persist the window geometry (debounced while dragging/resizing).

        Accepts and ignores arguments: connected both to the debounce timer and
        to ``Window.closing``, which passes a close event.
        """
        window = self._window
        if window is None or not self._get_remember_window():
            return
        maximized = window.windowState() == Qt.WindowState.WindowMaximized
        values: dict = {"window.maximized": maximized}
        if not maximized:
            # While maximized keep the last normal geometry, so un-maximizing
            # after a restart lands somewhere sensible.
            for key, name in (("window.width", "width"), ("window.height", "height"),
                              ("window.x", "x"), ("window.y", "y")):
                values[key] = int(window.property(name))
        self._store.update(values)
        self.changed.emit()

    @Slot()
    def resetWindow(self) -> None:
        """Forget the remembered window geometry (the window itself stays put)."""
        defaults = DEFAULTS["window"]
        self._store.update({
            "window.width": defaults["width"],
            "window.height": defaults["height"],
            "window.x": None,
            "window.y": None,
            "window.maximized": False,
        })
        self.changed.emit()

    # --- config file ------------------------------------------------------

    def _get_config_path(self) -> str:
        return str(self._store.path)

    def _get_config_mode(self) -> str:
        return "Portable" if self._store.is_portable else "System"

    def _get_warning(self) -> str:
        return self._store.warning

    @Slot()
    def openConfigFolder(self) -> None:
        """Open the folder holding the settings file."""
        folder = self._store.path.parent
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    @Slot()
    def resetToDefaults(self) -> None:
        """Restore every default and apply the result live."""
        self._store.reset()
        self._apply_appearance()
        self.accentChanged.emit()
        self.latexSizeChanged.emit()
        self.changed.emit()

    # --- properties -------------------------------------------------------

    theme = Property(str, _get_theme, _set_theme, notify=changed)
    backdrop = Property(str, _get_backdrop, _set_backdrop, notify=changed)
    accent = Property(str, _get_accent, _set_accent, notify=changed)
    latexSize = Property(int, _get_latex_size, _set_latex_size, notify=changed)
    rememberWindow = Property(
        bool, _get_remember_window, _set_remember_window, notify=changed
    )
    # Read once by MainWindow.qml to size the window at creation (see
    # _restore_geometry for why the size must not be assigned later).
    startupWidth = Property(int, _get_startup_width, constant=True)
    startupHeight = Property(int, _get_startup_height, constant=True)
    configPath = Property(str, _get_config_path, constant=True)
    configMode = Property(str, _get_config_mode, constant=True)
    warning = Property(str, _get_warning, notify=changed)


