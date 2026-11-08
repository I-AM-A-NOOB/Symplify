"""Teaches RinUI's window manager to drag the title bar the way Windows does.

RinUI starts its custom-title-bar drag with::

    ReleaseCapture()
    SendMessage(hwnd, WM_SYSCOMMAND, SC_MOVE | HTCAPTION, 0)

``WM_SYSCOMMAND``'s ``lParam`` carries the cursor position for ``SC_MOVE``, so
zero tells Windows the pointer is at the screen origin. That goes unnoticed until
the window is maximized: the move un-maximizes it first, and Windows takes the
restore rectangle from that same point — so a maximized window dragged down lands
at the drag's offset from the *top-left corner of the screen* instead of under
the pointer. Measured on Windows 11 with the window maximized at (-11, -11) and
the pointer pressed at x = 1280: the window was released at x = 0, exactly the
drag delta.

``WM_NCLBUTTONDOWN`` with ``HTCAPTION`` is the message Windows itself produces for
a press on a real caption. It needs no cursor coordinates, and the drag it starts
is an ordinary caption drag — restore, Aero Snap and the rest included.

The override has to be a class, not a patched method: QML dispatches through the
meta-object, which is built when the class is created, so only a real subclass
with its own ``@Slot`` is reachable from ``WindowManager.qml``. It is installed by
replacing the name ``RinUI.core.window.WinEventManager`` — the launcher imports
that name *inside* the call that builds the manager, so the replacement is picked
up — and only after RinUI's own config takeover has run (see
:mod:`python.rinui_bootstrap`). Verified against RinUI 0.4.4.1; the title bar is
unchanged in 0.5.0, so the same override still applies.
"""

import ctypes
import sys

#: True on the only platform this module does anything on.
WINDOWS = sys.platform == "win32"

_WM_NCLBUTTONDOWN = 0x00A1
_WM_NCHITTEST = 0x0084
_HTCAPTION = 2
_HTCLIENT = 1
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_BORDER_COLOR = 34
_DWMWA_VISIBLE_FRAME_BORDER_THICKNESS = 37
_DWMWCP_DONOTROUND = 1
_DWMWCP_ROUND = 2
_DWMWA_COLOR_NONE = 0xFFFFFFFE
_DWMWA_COLOR_DEFAULT = 0xFFFFFFFF

_user32 = ctypes.WinDLL("user32", use_last_error=True) if WINDOWS else None
_dwmapi = ctypes.WinDLL("dwmapi") if WINDOWS else None
if _user32 is not None:
    # Without argtypes ctypes marshals hwnd as a C int and truncates it to 32
    # bits — a silently wrong window handle on 64-bit Windows.
    _user32.ReleaseCapture.argtypes = []
    _user32.ReleaseCapture.restype = ctypes.c_int
    _user32.SendMessageW.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p
    ]
    _user32.SendMessageW.restype = ctypes.c_void_p
if _dwmapi is not None:
    _dwmapi.DwmSetWindowAttribute.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint
    ]
    _dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long


def caption_press(hwnd: int) -> None:
    """Start a system move as if the user had pressed the window's caption."""
    if _user32 is None:  # not Windows: nothing to send
        return
    _user32.ReleaseCapture()
    _user32.SendMessageW(hwnd, _WM_NCLBUTTONDOWN, _HTCAPTION, 0)


def set_rounded_corners(hwnd: int, rounded: bool) -> None:
    """Ask DWM for square corners while the window is fullscreen.

    Windows 11 rounds every top-level window by default, including a borderless
    fullscreen one. QML can square RinUI's own background, but the native frame
    still carries a rounded corner unless this attribute is set. Windows 10
    ignores the unknown attribute; the call is harmless there.
    """
    if _dwmapi is None or not hwnd:
        return
    preference = ctypes.c_int(_DWMWCP_ROUND if rounded else _DWMWCP_DONOTROUND)
    _dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd),
        _DWMWA_WINDOW_CORNER_PREFERENCE,
        ctypes.byref(preference),
        ctypes.sizeof(preference),
    )
    #: Windows 11 also paints a one-pixel DWM border. A fullscreen surface has
    #: no caption/frame to separate from the desktop, so suppress it too.
    border = ctypes.c_uint(
        _DWMWA_COLOR_DEFAULT if rounded else _DWMWA_COLOR_NONE
    )
    _dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd),
        _DWMWA_BORDER_COLOR,
        ctypes.byref(border),
        ctypes.sizeof(border),
    )
    thickness = ctypes.c_uint(1 if rounded else 0)
    _dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd),
        _DWMWA_VISIBLE_FRAME_BORDER_THICKNESS,
        ctypes.byref(thickness),
        ctypes.sizeof(thickness),
    )


def install(base: type) -> type:
    """Replace ``base``'s ``drag_window_event`` with the caption-press version.

    Args:
        base: RinUI's ``WinEventManager``, imported by the caller so that this
            module never has to import ``RinUI`` itself.

    Returns:
        The subclass that was installed, or ``base`` unchanged off Windows.
    """
    if not WINDOWS:
        return base

    from PySide6.QtCore import QObject, QTimer, Slot

    class WinEventManager(base):
        """RinUI's manager, with a caption drag the system understands."""

        _drag_windows: list = []

        def set_windows(self, windows, on_window_frame_changed=None):
            self._drag_windows = list(windows or [])
            super().set_windows(windows, on_window_frame_changed)

        def _window_for(self, hwnd: int):
            for window in self._drag_windows:
                try:
                    if int(window.winId()) == hwnd:
                        return window
                except (RuntimeError, TypeError):
                    continue
            return None

        @Slot(QObject, bool)
        def set_window_corners(self, window: QObject, rounded: bool) -> None:
            try:
                set_rounded_corners(int(window.winId()), bool(rounded))
            except (RuntimeError, TypeError, AttributeError):
                pass

        @Slot(int)
        def drag_window_event(self, hwnd: int) -> None:
            """Press the caption, and tell the QML side a drag is in flight.

            RinUI's title bar starts that native drag on press, but its
            ``onPositionChanged`` *also* moves the window by hand — guarded by a
            platform test that returns off Windows rather than on it, so on
            Windows the manual move runs as well. Once the drag has un-maximized
            the window the handler's local coordinates no longer line up (they
            shift by half the width difference), and its ``window.x + delta``
            teleports the window. ``MainWindow.qml`` reads the ``dragInProgress``
            property this sets, so it has to stay raised until the mouse events
            the system move left queued have been handled — hence the zero-timer
            rather than clearing it here.
            """
            if not hwnd:
                return
            window = self._window_for(hwnd)
            if window is not None:
                window.setProperty("dragInProgress", True)
            try:
                caption_press(hwnd)
            finally:
                if window is not None:
                    QTimer.singleShot(
                        0, lambda: window.setProperty("dragInProgress", False)
                    )

    module = sys.modules[base.__module__]
    setattr(module, "WinEventManager", WinEventManager)
    return WinEventManager


#: Kept alive here: ``installNativeEventFilter`` does not take ownership.
_fullscreen_hit_test = None


def install_fullscreen_hit_test():
    """Keep the whole fullscreen surface in the window's client area.

    RinUI's window is frameless but still carries ``WS_THICKFRAME``, and Windows
    reports the top resize border as non-client (``HTTOP``) even when the window
    covers the screen. Measured on Windows 11 at 150% scaling: the top **8
    physical** pixels answer ``HTTOP``, so mouse moves there never reach QML at
    all — no hover and no clicks.

    That is exactly where the fullscreen Zen strip is reached from, and it is
    why the strip could appear and vanish: moving up, the pointer hovers it at
    y = 6..40; at the screen's top edge it enters the non-client border, the
    hover stops, and the strip hides; moving back out of the border delivers
    hover again (the strip appears), and leaving the strip hides it once more.

    Filters run in reverse installation order, so this one — installed after
    RinUI's own in ``window.load()`` — is asked first and can answer
    ``HTCLIENT`` for every point of a fullscreen window. That is the truth of
    the surface: a fullscreen window has no frame to resize or drag.

    Returns:
        The installed filter, or ``None`` off Windows or before an application
        exists. The module keeps its own reference, so the caller may ignore it.
    """
    global _fullscreen_hit_test
    if not WINDOWS or _fullscreen_hit_test is not None:
        return _fullscreen_hit_test

    from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication
    from PySide6.QtGui import QGuiApplication, QWindow

    class FullscreenHitTest(QAbstractNativeEventFilter):
        """Answer ``HTCLIENT`` for the whole surface of a fullscreen window."""

        def nativeEventFilter(self, event_type, message):
            if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                return False, 0
            try:
                address = int(message)
            except Exception:
                buffer = memoryview(message)
                address = ctypes.addressof(ctypes.c_char.from_buffer(buffer))
            hwnd = ctypes.c_void_p.from_address(address).value
            message_id = ctypes.c_uint.from_address(
                address + ctypes.sizeof(ctypes.c_void_p)
            ).value
            if message_id != _WM_NCHITTEST:
                return False, 0
            for window in QGuiApplication.topLevelWindows():
                try:
                    if int(window.winId()) != hwnd:
                        continue
                    if window.visibility() == QWindow.Visibility.FullScreen:
                        return True, _HTCLIENT
                except (RuntimeError, TypeError):
                    continue
                break
            return False, 0

    application = QCoreApplication.instance()
    if application is None:
        return None
    _fullscreen_hit_test = FullscreenHitTest()
    application.installNativeEventFilter(_fullscreen_hit_test)
    return _fullscreen_hit_test
