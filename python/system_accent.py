"""The OS accent as Qt reports it: the base colour and its scheme variants.

Capturing means temporarily switching the application's colour scheme, so it
happens once at startup — before the QML tree is loaded, which is what keeps
those switches invisible. ``SystemAccent`` owns that capture and the values it
produced; the viewmodel owns what they *mean* (which accent mode uses them and
whether the OS-shading option is on), which is why the option is passed in
rather than read here.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette


class SystemAccent:
    """The accent the OS reports, and the per-scheme values it ships."""

    def __init__(self) -> None:
        #: OS accent per colour scheme ({False: light, True: dark}), plus the
        #: ``base`` entry; empty when the platform cannot be asked for both
        #: (see :meth:`capture`).
        self.accents: dict = {}
        #: Re-entrancy guard: capturing switches the colour scheme, which emits
        #: paletteChanged, which would call back into the capture.
        self._capturing = False

    def base(self, fallback: str) -> str:
        """The system accent: the OS's **base** accent, not a scheme's variant.

        The shading derives both scheme variants from this, so feeding it a
        value that is already tuned for a scheme would darken or lighten twice.
        ``QPalette.Highlight`` under the **dark** scheme is the base — checked
        against the OS itself on two accents (`#258292` and `#0078d4`), where it
        matched `DWM\\AccentColor` and differed from `Accent`, which carries the
        per-scheme value.

        The captured value is preferred so the base does not move with the OS
        theme; the live palette is the fallback for a platform that cannot be
        asked to switch schemes, and ``fallback`` (RinUI's own colour) when
        there is no palette at all (headless tests).
        """
        if "base" in self.accents:
            return self.accents["base"]
        app = QGuiApplication.instance()
        if app is None:
            return fallback
        return QColor(app.palette().color(QPalette.ColorRole.Highlight)).name()

    def capture(self) -> None:
        """Record what the OS reports about the accent, once, at startup.

        Three values, all read before the QML tree is loaded so the temporary
        scheme switches are never visible:

        * ``base`` — ``Highlight`` under the **dark** scheme, the OS's untuned
          accent. Both shades derive from this, so it must not be a
          scheme-specific value or the result would be tuned twice.
        * ``light`` / ``dark`` — ``Accent`` under each scheme, i.e. the OS's own
          tuned accents. On Windows these are what the shell itself uses, so
          ``system`` mode prefers them (see :meth:`scheme`).

        The previous scheme is always restored, even if a switch fails: leaving
        the application in the wrong colour scheme would be far worse than a
        missing accent.
        """
        app = QGuiApplication.instance()
        if app is None or self._capturing:
            return
        hints = app.styleHints()
        self._capturing = True
        original = hints.colorScheme()
        captured: dict[str, str] = {}
        try:
            for scheme, keys in (
                (Qt.ColorScheme.Dark, ("base", "dark")),
                (Qt.ColorScheme.Light, ("light",)),
            ):
                hints.setColorScheme(scheme)
                palette = app.palette()
                for key in keys:
                    role = (QPalette.ColorRole.Highlight if key == "base"
                            else QPalette.ColorRole.Accent)
                    captured[key] = QColor(palette.color(role)).name()
        except Exception:
            captured = {}          # no usable scheme switching: fall back to live
        finally:
            try:
                hints.setColorScheme(original)
            except Exception:
                pass
            self._capturing = False
        self.accents = captured

    def scheme(self, dark: bool, os_shading: bool) -> str:
        """The OS's own accent for that scheme, or ``''`` when there is none.

        Windows ships a tuned accent per colour scheme and uses it itself, so for
        ``system`` mode that value beats our own derivation of it. Restricted to
        Windows on purpose: elsewhere the palette's accent is not scheme-specific
        (or not the user's theme colour at all), and the derivation stays
        predictable.

        ``os_shading`` is the viewmodel's ``appearance.accent_os_shading``
        option, which is how the behaviour is opted out of; the policy stays
        there and is passed in.
        """
        if sys.platform != "win32":
            return ""
        if not os_shading:
            return ""
        return self.accents.get("dark" if dark else "light", "")
