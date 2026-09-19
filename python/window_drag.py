# coding: utf-8
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
:mod:`python.rinui_bootstrap`). Verified against RinUI 0.4.4.1.
"""

import ctypes
import sys

#: True on the only platform this module does anything on.
WINDOWS = sys.platform == "win32"

_WM_NCLBUTTONDOWN = 0x00A1
_HTCAPTION = 2

_user32 = ctypes.WinDLL("user32", use_last_error=True) if WINDOWS else None
if _user32 is not None:
    # Without argtypes ctypes marshals hwnd as a C int and truncates it to 32
    # bits — a silently wrong window handle on 64-bit Windows.
    _user32.ReleaseCapture.argtypes = []
    _user32.ReleaseCapture.restype = ctypes.c_int
    _user32.SendMessageW.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p
    ]
    _user32.SendMessageW.restype = ctypes.c_void_p


def caption_press(hwnd: int) -> None:
    """Start a system move as if the user had pressed the window's caption."""
    if _user32 is None:  # not Windows: nothing to send
        return
    _user32.ReleaseCapture()
    _user32.SendMessageW(hwnd, _WM_NCLBUTTONDOWN, _HTCAPTION, 0)


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

    from PySide6.QtCore import QTimer, Slot

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
