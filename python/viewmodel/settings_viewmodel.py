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

import sys
from typing import Optional, Tuple
from functools import lru_cache

from PySide6.QtCore import Property, QObject, QPoint, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QPalette,
)

from ..accent import for_scheme, variants
from ..fonts import (
    CODE_GLYPHS,
    expand_keyword,
    math_font_choices,
    math_font_path,
    split_families,
)
from ..keyboard_config import label_glyphs
from ..settings import DEFAULTS, SettingsStore


@lru_cache(maxsize=128)
def _family_missing_glyphs(family: str, glyphs: str) -> str:
    """Which of ``glyphs`` one family cannot draw, via ``QRawFont``.

    ``glyphIndexesForString`` returns glyph 0 (.notdef) for a character the
    typeface has no glyph for, which is the honest question for a font family.
    The obvious ``QFontMetrics.inFont()`` is unusable instead: it answers ``True``
    for every character of every family (Qt's substitution hides the gap). Cached
    because building a ``QRawFont`` reads the font file.
    """
    from PySide6.QtGui import QFont, QRawFont

    raw = QRawFont.fromFont(QFont(family))
    if not raw.isValid():
        return glyphs
    return "".join(
        char for char in glyphs if raw.glyphIndexesForString(char)[0] == 0
    )


def _chain_missing_glyphs(families: str, glyphs: str) -> str:
    """Glyphs **no** family in the preference list can draw.

    The list is a real Qt fallback chain, so a glyph missing from the first face
    is drawn by a later one; only a glyph no entry has would show as a tofu box.
    Without a running application there is nothing to measure, so the answer is
    "nothing missing" rather than a false accusation.
    """
    if not glyphs or QGuiApplication.instance() is None:
        return ""
    chain = installed_chain(families)
    if not chain:
        return glyphs
    return "".join(
        char
        for char in glyphs
        if all(char in _family_missing_glyphs(family, char) for family in chain)
    )


def installed_chain(families: str) -> list:
    """The installed families of a preference list, in order, keywords expanded.

    This is exactly the chain Qt resolves characters against when the list is
    handed to ``QFont.setFamilies``, so it is also what :func:`_chain_missing_glyphs`
    has to walk. Empty without a running application —
    ``QFontDatabase.families()`` aborts the process rather than raising.
    """
    if QGuiApplication.instance() is None:
        return []
    installed = {name.casefold() for name in QFontDatabase.families()}
    return list(dict.fromkeys(
        candidate
        for name in split_families(families)
        for candidate in expand_keyword(name)
        if candidate.casefold() in installed
    ))


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
        #: OS accent per colour scheme ({False: light, True: dark}); empty when
        #: the platform cannot be asked for both (see _capture_system_accents).
        self._system_accents: dict = {}
        #: Re-entrancy guard: capturing switches the colour scheme, which emits
        #: paletteChanged, which would call back into the capture.
        self._capturing_accents = False
        self._theme_manager = theme_manager
        self._window: Optional[QObject] = None
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.setInterval(500)
        self._geometry_timer.timeout.connect(self._save_geometry)

        #: The colour picked by the picker, held here until the drag settles —
        #: see _set_custom_accent. None means the store is authoritative.
        self._pending_accent: Optional[str] = None
        self._accent_timer = QTimer(self)
        self._accent_timer.setSingleShot(True)
        self._accent_timer.setInterval(400)
        self._accent_timer.timeout.connect(self._flush_pending_accent)
        # Appearance is NOT re-applied here: the bootstrap already injected it into
        # RinUI's config before the window existed, and applying a backdrop needs a
        # window handle (RinUI warns and refuses without one). _apply_appearance is
        # for after-the-fact changes, i.e. restore-defaults.
        #
        # The palette, though, can only be read once an application exists: it is
        # what the `system` accent mode reports, so a change to the OS accent has
        # to be followed while that mode is active.
        app = QGuiApplication.instance()
        if app is not None:
            # Capture before connecting: the switch below would otherwise emit
            # paletteChanged and re-enter this object.
            self._capture_system_accents()
            app.paletteChanged.connect(self._on_palette_changed)

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

    def _get_accent_mode(self) -> str:
        """Which accent the UI uses: ``default`` / ``system`` / ``custom``."""
        return self._store.get("appearance.accent_mode")

    def _set_accent_mode(self, mode: str) -> None:
        self._store.set("appearance.accent_mode", mode)
        self.accentChanged.emit()
        self.changed.emit()

    def _get_custom_accent(self) -> str:
        """The colour the user picked, kept while another mode is active.

        A pending write wins: the picker changes the colour on every mouse move
        while it is dragged, and reading straight from the store would show the
        last *persisted* value, so the colour would visibly snap back mid-drag.
        """
        if self._pending_accent is not None:
            return self._pending_accent
        return self._store.get("appearance.accent")

    def _set_custom_accent(self, accent: str) -> None:
        """Take a picked colour (invalid input is ignored) and persist it lazily.

        The write is debounced because a picker drag emits a change per mouse
        move, and each one would otherwise rewrite the config file. The value in
        effect updates immediately — the accent applies live and the preview
        follows — so only the disk write waits.
        """
        color = QColor(accent)
        if not color.isValid():
            return
        self._pending_accent = color.name()
        self._accent_timer.start()
        if self._get_accent_mode() == "custom":
            self.accentChanged.emit()
        self.changed.emit()

    def _flush_pending_accent(self, *_) -> None:
        """Write the debounced colour, if there is one."""
        if self._pending_accent is None:
            return
        pending, self._pending_accent = self._pending_accent, None
        self._store.set("appearance.accent", pending)

    def _get_accent(self) -> str:
        """The accent colour that is actually in effect, mode resolved.

        This is what the QML side hands to RinUI's ``Theme.setThemeColor``.
        """
        mode = self._get_accent_mode()
        if mode == "system":
            return self._system_accent()
        if mode == "custom":
            return self._get_custom_accent()
        return DEFAULTS["appearance"]["accent"]

    def _system_accent(self) -> str:
        """The system accent: the OS's **base** accent, not a scheme's variant.

        The shading below derives both scheme variants from this, so feeding it a
        value that is already tuned for a scheme would darken or lighten twice.
        ``QPalette.Highlight`` under the **dark** scheme is the base — checked
        against the OS itself on two accents (`#258292` and `#0078d4`), where it
        matched `DWM\\AccentColor` and differed from `Accent`, which carries the
        per-scheme value.

        The captured value is preferred so the base does not move with the OS
        theme; the live palette is the fallback for a platform that cannot be
        asked to switch schemes, and RinUI's own colour when there is no palette
        at all (headless tests).
        """
        if "base" in self._system_accents:
            return self._system_accents["base"]
        app = QGuiApplication.instance()
        if app is None:
            return DEFAULTS["appearance"]["accent"]
        return QColor(app.palette().color(QPalette.ColorRole.Highlight)).name()

    def _capture_system_accents(self) -> None:
        """Record what the OS reports about the accent, once, at startup.

        Three values, all read before the QML tree is loaded so the temporary
        scheme switches are never visible:

        * ``base`` — ``Highlight`` under the **dark** scheme, the OS's untuned
          accent. The blends derive from this, so it must not be a
          scheme-specific value or the result would be tuned twice.
        * ``light`` / ``dark`` — ``Accent`` under each scheme, i.e. the OS's own
          tuned accents. On Windows these are what the shell itself uses, so
          ``system`` mode prefers them (see ``_system_scheme_accent``).

        The previous scheme is always restored, even if a switch fails: leaving
        the application in the wrong colour scheme would be far worse than a
        missing accent.
        """
        app = QGuiApplication.instance()
        if app is None or self._capturing_accents:
            return
        hints = app.styleHints()
        self._capturing_accents = True
        original = hints.colorScheme()
        captured: Dict[str, str] = {}
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
            self._capturing_accents = False
        self._system_accents = captured

    def _system_scheme_accent(self, dark: bool) -> str:
        """The OS's own accent for that scheme, or ``''`` when there is none.

        Windows ships a tuned accent per colour scheme and uses it itself, so for
        ``system`` mode that value beats anything we could blend. Restricted to
        Windows on purpose: elsewhere the palette's accent is not scheme-specific
        (or not the user's theme colour at all), and the blends stay predictable.
        Also off when ``appearance.accent_os_shading`` is off, which is how the
        behaviour is opted out of.
        """
        if sys.platform != "win32":
            return ""
        if not self._get_accent_os_shading():
            return ""
        return self._system_accents.get("dark" if dark else "light", "")

    @Slot(bool, result=str)
    def accentForScheme(self, dark: bool) -> str:
        """The accent to apply for a theme of the given lightness.

        ``default`` and ``custom`` are colours the OS knows nothing about, so they
        take the blends (``for_scheme``: darker for light, lighter for dark) —
        the same for every platform. ``system`` on Windows uses the OS's own
        tuned accent for the scheme instead, since the shell uses it too and no
        blend reproduces it; on any other platform ``system`` blends as well.

        Shading off means no per-scheme finetuning at all: the base verbatim.
        """
        base = self._get_accent()
        if not self._get_accent_shading():
            return base
        if self._get_accent_mode() == "system":
            from_os = self._system_scheme_accent(bool(dark))
            if from_os:
                return from_os
        return for_scheme(base, bool(dark))

    def _get_accent_preview(self) -> list:
        """The swatches the settings page shows beside the colour control.

        A preview, not a control: it follows the accent the UI is using (not the
        stored custom colour the dropdown next to it edits), and it shows the
        palette actually in play — the OS's dark/base/light trio in ``system``
        mode on Windows, our blended trio otherwise, and a single flat swatch
        when shading is off.
        """
        base = self._get_accent()
        if not self._get_accent_shading():
            return [base]
        if self._get_accent_mode() == "system" and self._get_accent_os_shading():
            dark = self._system_scheme_accent(True)
            light = self._system_scheme_accent(False)
            if dark and light:
                return [light, base, dark]      # darkest to lightest
        return list(variants(base))

    def _on_palette_changed(self, *_) -> None:
        """Follow the OS accent while the ``system`` mode is active."""
        self._capture_system_accents()
        if self._get_accent_mode() == "system":
            self.accentChanged.emit()
            self.changed.emit()

    # --- fonts ------------------------------------------------------------

    def _get_code_family(self) -> str:
        return self._store.get("fonts.code_family")

    def _set_code_family(self, families: str) -> None:
        self._store.set("fonts.code_family", families)
        self.changed.emit()

    def _get_code_size(self) -> int:
        return int(self._store.get("fonts.code_size"))

    def _set_code_size(self, size: int) -> None:
        self._store.set("fonts.code_size", size)
        self.changed.emit()

    def _get_keyboard_family(self) -> str:
        return self._store.get("fonts.keyboard_family")

    def _set_keyboard_family(self, families: str) -> None:
        self._store.set("fonts.keyboard_family", families)
        self.changed.emit()

    def _get_keyboard_size(self) -> int:
        return int(self._store.get("fonts.keyboard_size"))

    def _set_keyboard_size(self, size: int) -> None:
        self._store.set("fonts.keyboard_size", size)
        self.changed.emit()

    def _get_accent_shading(self) -> bool:
        return bool(self._store.get("appearance.accent_shading"))

    def _set_accent_shading(self, enabled: bool) -> None:
        """Toggle the WinUI-style per-scheme finetuning of the accent."""
        self._store.set("appearance.accent_shading", bool(enabled))
        # The applied colour changes with it, so announce the accent too.
        self.accentChanged.emit()
        self.changed.emit()

    def _get_accent_os_shading(self) -> bool:
        return bool(self._store.get("appearance.accent_os_shading"))

    def _set_accent_os_shading(self, enabled: bool) -> None:
        """Prefer the OS's own per-scheme accent over our blend."""
        self._store.set("appearance.accent_os_shading", bool(enabled))
        self.accentChanged.emit()
        self.changed.emit()

    def _get_accent_os_shading_supported(self) -> bool:
        """Whether this platform has OS accents at all — Windows, and only it.

        The row is hidden entirely elsewhere rather than shown permanently
        disabled: on a platform with no per-scheme accent it could never be
        turned on, and a dead control is worse than an absent one.
        """
        return sys.platform == "win32"

    def _get_accent_os_shading_available(self) -> bool:
        """Whether the option would actually take effect right now.

        Three conditions, all required: Windows, the **system** accent selected
        (the OS only has an opinion about its own colour), and per-theme shading
        on (with it off nothing is finetuned at all). The settings row states
        these, since a disabled switch otherwise looks broken. The OS values must
        also have been captured, or there is nothing to prefer.
        """
        if not self._get_accent_os_shading_supported():
            return False
        if self._get_accent_mode() != "system":
            return False
        if not self._get_accent_shading():
            return False
        return bool(self._system_scheme_accent(True) and self._system_scheme_accent(False))

    def _get_latex_font(self) -> str:
        return self._store.get("fonts.latex_font")

    def _set_latex_font(self, family: str) -> None:
        self._store.set("fonts.latex_font", family)
        self.changed.emit()

    def _get_code_font_family(self) -> str:
        """The primary family of the code list (for display: "In use: …")."""
        return self._first_installed(self._get_code_family())

    def _get_keyboard_font_family(self) -> str:
        """The primary family of the keyboard list (for display)."""
        return self._first_installed(self._get_keyboard_family())

    def _get_code_font(self) -> QFont:
        """The code font, as a real Qt font with the whole family list.

        ``QFont.setFamilies`` is what makes a *fallback* a fallback: Qt then
        resolves each character against the families in order, so a glyph the
        first face lacks is drawn from the next one that has it. QML cannot
        express this — its ``font`` value type has no ``families``, only a single
        ``family`` — so the font is built here and the pages bind
        ``font: settingsVM.codeFont``. Passing the list through unmodified also
        means an uninstalled name is simply skipped by Qt, exactly as the user
        would expect.
        """
        return self._build_font(self._get_code_family(), self._get_code_size())

    def _get_keyboard_font(self) -> QFont:
        """The keyboard font, as a real Qt font with the whole family list."""
        return self._build_font(
            self._get_keyboard_family(), self._get_keyboard_size()
        )

    def _build_font(self, families: str, size: int) -> QFont:
        """A ``QFont`` carrying ``families`` (keywords expanded) and ``size``.

        The names go in unmodified — a name Qt cannot find is simply skipped
        during lookup, so the user sees exactly the fallback behaviour they
        wrote. Generic keywords are expanded first, because ``"monospace"`` is
        not a family Qt can look up, and the result is de-duplicated while
        keeping order (a keyword's candidates routinely repeat a family the user
        also named, and repeating it in the chain buys nothing).
        """
        font = QFont()
        names = [
            candidate
            for name in split_families(families)
            for candidate in expand_keyword(name)
        ]
        if names:
            font.setFamilies(list(dict.fromkeys(names)))
        font.setPixelSize(int(size))
        return font

    def _installed_chain(self, families: str) -> list:
        """The installed families of a list, in order (keywords expanded).

        This is the chain Qt resolves characters against, so it is also what the
        coverage report walks. See ``installed_chain`` at module level.
        """
        return installed_chain(families)

    def _first_installed(self, families: str) -> str:
        """The first installed family of a list (for display only).

        The list is what the user types; a missing family is skipped so the note
        names something that exists. With no application (headless tests) the
        first name is returned unchanged — ``QFontDatabase.families()`` aborts
        the process rather than raising when there is none.
        """
        names = split_families(families)
        if not names:
            return ""
        if QGuiApplication.instance() is None:
            return names[0]
        chain = self._installed_chain(families)
        return chain[0] if chain else names[0]

    def _get_code_fallback_count(self) -> int:
        """How many further installed faces back up the code font's primary one."""
        return max(0, len(self._installed_chain(self._get_code_family())) - 1)

    def _get_keyboard_fallback_count(self) -> int:
        """How many further installed faces back up the keyboard font's primary."""
        return max(0, len(self._installed_chain(self._get_keyboard_family())) - 1)

    def _get_code_missing_glyphs(self) -> str:
        """Glyphs no family in the code chain can draw ('' when the chain covers all).

        Fallback-aware: a glyph is only reported when *every* family in the list
        lacks it, because that is the case Qt cannot rescue.
        """
        return _chain_missing_glyphs(self._get_code_family(), CODE_GLYPHS)

    def _get_keyboard_missing_glyphs(self) -> str:
        """Glyphs no family in the keyboard chain can draw.

        Measured against the glyphs the layout actually shows
        (`keyboard_config.label_glyphs`), which is the only place a missing
        character would be visible.
        """
        return _chain_missing_glyphs(self._get_keyboard_family(), label_glyphs())

    def _get_latex_font_path(self) -> str:
        """The font *file* to hand ziamath ('' = its bundled STIX Two Math).

        Resolved on read: turning a family into a path is a filesystem lookup
        (and, for a font inside a collection, a one-off extraction).
        """
        return math_font_path(self._get_latex_font()) or ""

    def _get_math_fonts(self) -> list:
        """Names of the installed fonts that can render math, for the dropdown.

        Read once per page build; the underlying scan is cached in
        ``python/fonts.py``. The page prepends its own "Default" entry.
        """
        return [choice["family"] for choice in math_font_choices()]

    # --- rendering --------------------------------------------------------

    def _get_latex_size(self) -> int:
        return int(self._store.get("fonts.latex_size"))

    def _set_latex_size(self, size: int) -> None:
        self._store.set("fonts.latex_size", size)
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
        """Move the window to its remembered position, unless it starts maximized.

        The *size* is not set here on purpose: it comes from
        ``MainWindow.qml``'s ``width``/``height`` bindings (see
        :attr:`startupWidth`). Resizing the window at this point — while it is
        still being created — and then maximizing it leaves the presentation
        stale on Windows: the window fills the screen and Qt reports the right
        sizes, but what is drawn stays in the old rectangle with a white border,
        and later resizes do not repair it. Verified against RinUI 0.4.4.1.

        When the remembered state is maximized the position is left alone as
        well: the platform places the window, so dragging it out of fullscreen
        lands where the system put it instead of jumping to a position from
        before. The size is still remembered, which is what that window becomes.
        """
        window = self._window
        if window is None:
            return
        maximized = bool(self._store.get("window.maximized"))
        if not maximized:
            x, y = self._store.get("window.x"), self._store.get("window.y")
            if x is not None and y is not None and self._is_on_a_screen(int(x), int(y)):
                window.setProperty("x", int(x))
                window.setProperty("y", int(y))
        else:
            # Maximizing before the window is shown has the same stale-surface
            # effect as resizing it, so the state is applied once the window is
            # actually shown. MainWindow.qml declares `visible: true`, so at this
            # point it usually already is — hence the timer fallback rather than
            # only the signal.
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
    # `accent` is the colour in effect (mode resolved) and read-only: the modes
    # above decide it, `customAccent` is the only part the user picks directly.
    accent = Property(str, _get_accent, notify=changed)
    accentMode = Property(
        str, _get_accent_mode, _set_accent_mode, notify=changed
    )
    accentShading = Property(
        bool, _get_accent_shading, _set_accent_shading, notify=changed
    )
    # Whether the OS's own accents may be used instead of our blend, whether the
    # option exists on this platform at all, and whether it would take effect.
    accentOsShading = Property(
        bool, _get_accent_os_shading, _set_accent_os_shading, notify=changed
    )
    accentOsShadingSupported = Property(
        bool, _get_accent_os_shading_supported, notify=changed
    )
    accentOsShadingAvailable = Property(
        bool, _get_accent_os_shading_available, notify=changed
    )
    customAccent = Property(
        str, _get_custom_accent, _set_custom_accent, notify=changed
    )
    latexSize = Property(int, _get_latex_size, _set_latex_size, notify=changed)
    # Typography. `*Family` is the preference list the user typed (read back
    # verbatim, so a fallback chain survives an edit); `*FontFamily` is the one
    # family QML can use, resolved to the first installed entry. `latexFontPath`
    # is a font FILE for ziamath, not a family.
    codeFamily = Property(str, _get_code_family, _set_code_family, notify=changed)
    codeFontFamily = Property(str, _get_code_font_family, notify=changed)
    codeSize = Property(int, _get_code_size, _set_code_size, notify=changed)
    keyboardFamily = Property(
        str, _get_keyboard_family, _set_keyboard_family, notify=changed
    )
    keyboardFontFamily = Property(str, _get_keyboard_font_family, notify=changed)
    # Glyphs that *no* family in the chain can draw ('' = the chain covers them
    # all). Reported per chain, not per family: a gap in the primary face is not
    # a problem when Qt falls back for it — see _chain_missing_glyphs.
    codeMissingGlyphs = Property(str, _get_code_missing_glyphs, notify=changed)
    keyboardMissingGlyphs = Property(
        str, _get_keyboard_missing_glyphs, notify=changed
    )
    # The fonts themselves, as QFont values carrying the whole family list so Qt
    # performs real per-character fallback. QML's `font` group cannot express a
    # list, so pages bind `font: settingsVM.codeFont` instead of setting a family.
    codeFont = Property(QFont, _get_code_font, notify=changed)
    keyboardFont = Property(QFont, _get_keyboard_font, notify=changed)
    # How many further installed faces back up the primary one — shown as
    # "fallbacks: N" so the chain is visible without opening the config file.
    codeFallbackCount = Property(int, _get_code_fallback_count, notify=changed)
    keyboardFallbackCount = Property(
        int, _get_keyboard_fallback_count, notify=changed
    )
    keyboardSize = Property(
        int, _get_keyboard_size, _set_keyboard_size, notify=changed
    )
    # The swatch strip beside the colour control: the WinUI variant family when
    # shading is on, the single flat colour when it is off. Read-only, and it
    # follows the accent in use rather than the stored custom colour.
    accentPreview = Property("QVariantList", _get_accent_preview, notify=changed)
    latexFont = Property(str, _get_latex_font, _set_latex_font, notify=changed)
    latexFontPath = Property(str, _get_latex_font_path, notify=changed)
    # The system fonts that can render math, for the LaTeX font dropdown. Read
    # once per page build (the scan behind it is cached); it only changes when
    # the user installs a font, which a restart picks up.
    mathFonts = Property("QVariantList", _get_math_fonts, constant=True)
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


