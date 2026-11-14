"""Window settings: whether the geometry is remembered, and the remembered one.

Methods only. The ``Property`` declarations, ``Signal`` objects and the timers
(``self._geometry_timer``) live on ``SettingsViewModel`` (the QObject subclass),
so shiboken registers them; this module is mixed in and refers to them through
``self``. Every setter here emits ``windowChanged`` and the catch-all ``changed``.
"""

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Slot
from PySide6.QtGui import QGuiApplication

from ..settings import DEFAULTS


class WindowSettings:
    """Applies and persists the remembered window geometry."""

    def _get_zen_fullscreen(self) -> bool:
        return bool(self._store.get("workspace.zen_fullscreen"))

    def _set_zen_fullscreen(self, enabled: bool) -> None:
        self._store.set("workspace.zen_fullscreen", bool(enabled))
        self.windowChanged.emit()
        self.changed.emit()

    @Slot(bool)
    def setGeometryTracking(self, enabled: bool) -> None:
        """Suspend geometry persistence around a fullscreen Zen transition."""
        enabled = bool(enabled)
        if enabled == self._geometry_tracking_enabled:
            return
        if not enabled:
            self._geometry_timer.stop()
            self._save_geometry()
        self._geometry_tracking_enabled = enabled
        if enabled:
            self._geometry_timer.start()

    def _get_remember_window(self) -> bool:
        return bool(self._store.get("window.remember"))

    def _set_remember_window(self, remember: bool) -> None:
        self._store.set("window.remember", remember)
        if remember:
            # Start remembering the current geometry AND wire the tracking
            # signals: turning the toggle on mid-session must behave exactly
            # like starting with it on (attachWindow skips the wiring when the
            # toggle was off at startup).
            self._save_geometry()
            self._wire_geometry()
        self.windowChanged.emit()
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
        self._wire_geometry()

    def _wire_geometry(self) -> None:
        """Connect the geometry-tracking signals once (idempotent)."""
        window = self._window
        if window is None or self._geometry_wired:
            return
        self._geometry_wired = True
        for signal_name in ("widthChanged", "heightChanged", "xChanged", "yChanged"):
            getattr(window, signal_name).connect(self._on_geometry_changed)
        window.closing.connect(self._save_geometry)

    def _on_geometry_changed(self, *_) -> None:
        """Restart the debounce (window signals carry the new value as an int)."""
        if self._geometry_tracking_enabled:
            self._geometry_timer.start()

    def _restore_geometry(self) -> None:
        """Move the window to its remembered position, then maximize if it was.

        The *size* is not set here on purpose: it comes from
        ``MainWindow.qml``'s ``width``/``height`` bindings (see
        :attr:`startupWidth`). Resizing the window at this point — while it is
        still being created — and then maximizing it leaves the presentation
        stale on Windows: the window fills the screen and Qt reports the right
        sizes, but what is drawn stays in the old rectangle with a white border,
        and later resizes do not repair it. Verified against RinUI 0.4.4.1; the window base is
        unchanged in 0.5.0.

        The *position* is applied even when the window starts maximized, because
        Qt hands the window's declared x/y to the platform as its normal
        geometry — the rect a maximized window returns to when it is restored
        rather than dragged out. Left unset (the QML default is 0, 0) that rect
        is the screen's corner, so a window that started maximized dropped there
        on the first restore instead of where it had been.
        """
        window = self._window
        if window is None:
            return
        x, y = self._store.get("window.x"), self._store.get("window.y")
        if x is not None and y is not None and self._is_on_a_screen(int(x), int(y)):
            window.setProperty("x", int(x))
            window.setProperty("y", int(y))
        if not bool(self._store.get("window.maximized")):
            return
        # Maximizing before the window is shown has the same stale-surface
        # effect as resizing it, so the state is applied once the window is
        # actually shown. MainWindow.qml declares `visible: true`, so at this
        # point it usually already is — hence the timer fallback rather than
        # only the signal.
        if window.property("visible"):
            QTimer.singleShot(0, self._apply_maximized_once)
        else:
            window.visibleChanged.connect(self._apply_maximized_once)
            self._maximized_connected = True

    def _apply_maximized_once(self, *_) -> None:
        """Maximize after the window is shown, then stop listening."""
        window = self._window
        if window is None or not window.property("visible"):
            return
        if self._maximized_connected:
            self._maximized_connected = False
            try:
                window.visibleChanged.disconnect(self._apply_maximized_once)
            except (RuntimeError, TypeError):
                pass
        window.showMaximized()

    def _startup_size(self) -> tuple[int, int]:
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
        if (window is None or not self._geometry_tracking_enabled
                or not self._get_remember_window()):
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
        self.windowChanged.emit()
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
        self.windowChanged.emit()
        self.changed.emit()
