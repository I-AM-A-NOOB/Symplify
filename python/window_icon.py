"""Put the application's icon on the window *class*, on Windows.

**Why this is needed at all.** `QApplication.setWindowIcon` does not put an icon
on a window — measured on the live HWND, `WM_GETICON` holds nothing until
something calls `QWindow.setIcon`, and Qt does not do that on its own. What the
shell shows before that is the *class* icon: the one `RegisterClassEx` was given
when Qt registered its window class, which is `IDI_APPLICATION`, an empty square.

That is the whole of the "Qt's default icon until the window has finished
rendering" — and, because the taskbar takes its button's icon from this fallback
when it is created, "sometimes the icon never appears" too. `main.py` re-asserts
`setIcon` after the QML has built the window, which makes the shell re-read it;
setting the class icons as well means the fallback is already ours, so there is
no window of time in which the wrong icon can be picked up.

The class is shared by every window this process creates, which is exactly right
here: one window, one icon. `LoadImageW` reads our own `.ico` — the file Nuitka
embeds in the exe — so the two cannot drift.

Windows only; a no-op everywhere else, and never raises: an icon is not worth
failing a start over.
"""

import ctypes
import sys
from pathlib import Path

#: `Get/SetClassLongPtrW` indices.
_GCLP_HICON = -14
_GCLP_HICONSM = -34
#: `LoadImageW`: load an icon from a file.
_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010
#: `GetSystemMetrics`: the sizes Windows asks a window's icons to be.
_SM_CXICON, _SM_CYICON = 11, 12
_SM_CXSMICON, _SM_CYSMICON = 49, 50


def apply_to_window_class(window, ico_path: Path) -> bool:
    """Make ``ico_path`` the class icon of ``window``'s window class.

    Returns whether it worked; ``False`` on any non-Windows platform, on a
    32-bit interpreter (where the class-icon calls have different names), or if
    the file will not load.
    """
    if sys.platform != "win32" or not (sys.maxsize > 2 ** 32):
        return False
    if not Path(ico_path).is_file():
        return False

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                      ctypes.c_uint, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_uint]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.SetClassLongPtrW.restype = ctypes.c_void_p
        user32.SetClassLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                            ctypes.c_void_p]

        hwnd = ctypes.c_void_p(int(window.winId()))
        path = str(ico_path)
        # Both sizes Windows asks for: the small one is the taskbar button, the
        # big one Alt+Tab and the shell's larger views.
        big = user32.LoadImageW(None, path, _IMAGE_ICON,
                                user32.GetSystemMetrics(_SM_CXICON),
                                user32.GetSystemMetrics(_SM_CYICON),
                                _LR_LOADFROMFILE)
        small = user32.LoadImageW(None, path, _IMAGE_ICON,
                                  user32.GetSystemMetrics(_SM_CXSMICON),
                                  user32.GetSystemMetrics(_SM_CYSMICON),
                                  _LR_LOADFROMFILE)
        if not big or not small:
            return False

        user32.SetClassLongPtrW(hwnd, _GCLP_HICON, big)
        user32.SetClassLongPtrW(hwnd, _GCLP_HICONSM, small)
        return True
    except Exception:
        # Best effort: the window keeps its own icon either way, and a start is
        # not the place to argue about an icon.
        return False
