"""Settings viewmodel: the settings store on one side, RinUI and QML on the other.

The store (``python/settings.py``) is the single source of truth; RinUI's own
persistence is taken over at import time by ``python/rinui_bootstrap.py``. This
viewmodel is the **only** writer of settings: every setter stores the value and
applies it live, so the file and the running UI cannot disagree.

The methods are grouped by domain into mixins — ``AppearanceSettings`` (theme,
accent, code colours, watermarks), ``FontSettings`` (the three faces, their
fallback chains and coverage), ``WindowSettings`` (the remembered geometry) and
``KeyboardSettings`` (the custom keyboard folder) — while every ``Property``,
``Signal`` and piece of shared state stays on this ``QObject`` subclass, so
shiboken registers them and QML sees one object.

Each domain has its own notify signal (``appearanceChanged``, ``fontsChanged``,
``windowChanged``, ``keyboardChanged``, ``configChanged``); every setter emits
its domain signal **and** ``changed``, which remains the "some setting moved"
signal ``MainViewModel`` listens on.

Appearance is applied through RinUI's ``ThemeManager`` QObject (the QML ``Theme``
singleton is a thin wrapper around it), which is why the window's theme manager is
passed in rather than reached for globally. Rendering settings are applied by
``MainViewModel``, which owns the viewmodels that render.
"""

import time
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QObject,
    QTimer,
    QTranslator,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication

from ..localization import (
    RINUI_TRANSLATION_PREFIX,
    SYSTEM_LANGUAGE,
    available_languages,
    language_name,
    resolve_language,
    translation_file,
)
from ..settings import SettingsStore
from ..system_accent import SystemAccent
from .settings_appearance import AppearanceSettings
from .settings_fonts import FontSettings
from .settings_keyboard import KeyboardSettings
from .settings_window import WindowSettings


class SettingsViewModel(
    AppearanceSettings,
    FontSettings,
    WindowSettings,
    KeyboardSettings,
    QObject,
):
    """Applies and persists the user settings.

    Signals:
        changed: Any setting changed, including the config-write status.
        appearanceChanged: Theme, backdrop, accent, code theme, brackets or the
            result watermark changed.
        fontsChanged: One of the fonts, its size or its chain/coverage changed.
        windowChanged: The remembered window geometry changed.
        keyboardChanged: The selected custom keyboard layout changed.
        configChanged: The config-write status (its warning) changed.
        latexSizeChanged: The result font size changed (renderers must re-render).
    """

    changed = Signal()
    appearanceChanged = Signal()
    fontsChanged = Signal()
    windowChanged = Signal()
    keyboardChanged = Signal()
    configChanged = Signal()
    latexSizeChanged = Signal()
    latexFontErrorChanged = Signal()
    accentChanged = Signal()
    languageChanged = Signal()
    keyboardLayoutsChanged = Signal()
    keyboardErrorChanged = Signal()

    def __init__(
        self,
        store: SettingsStore,
        theme_manager: QObject | None = None,
        parent: QObject | None = None,
        translation_dir: Path | None = None,
    ):
        """Initialize the settings viewmodel.

        Args:
            store: The loaded settings store.
            theme_manager: RinUI's ``ThemeManager``; when None (tests) appearance
                is still persisted but not applied to the running UI.
            translation_dir: Folder holding ``symplify_<code>.qm`` files; the
                repository's ``i18n/`` by default. It also holds the
                ``rinui_<code>.qm`` fragments (see _apply_rinui_language).
        """
        super().__init__(parent)
        self._store = store
        #: The family the last refused pick named, for the page's dialog.
        self._latex_font_error = ""
        #: Why creating/opening the custom keyboard folder failed, if it did.
        self._keyboard_error = ""
        #: OS accent per colour scheme, plus the base (see SystemAccent.capture);
        #: ``_system_accents`` below is a view of its dict.
        self._system_accent = SystemAccent()
        self._theme_manager = theme_manager
        self._translation_dir = (
            Path(translation_dir) if translation_dir is not None
            else Path(__file__).resolve().parents[2] / "i18n"
        )
        self._translator: QTranslator | None = None
        self._rinui_translator: QTranslator | None = None
        self._languages = available_languages(self._translation_dir)
        self._window: QObject | None = None
        self._geometry_wired = False
        #: True only while `_apply_maximized_once` listens on visibleChanged;
        #: disconnecting a signal that was never connected makes PySide print a
        #: `RuntimeWarning` instead of raising, which the Log page would show.
        self._maximized_connected = False
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.setInterval(500)
        self._geometry_timer.timeout.connect(self._save_geometry)
        #: MainWindow disables this while Zen mode is full screen; otherwise the
        #: fullscreen rect would overwrite the remembered normal geometry.
        self._geometry_tracking_enabled = True

        #: The colour picked by the picker, held here until the drag settles —
        #: see _set_custom_accent. None means the store is authoritative.
        self._pending_accent: str | None = None
        self._accent_timer = QTimer(self)
        self._accent_timer.setSingleShot(True)
        self._accent_timer.setInterval(400)
        self._accent_timer.timeout.connect(self._flush_pending_accent)
        #: The three size setters fire once per spin-box step. Their values must
        #: be live immediately, but the YAML write is coalesced: the first step
        #: writes at once, the rest of the burst once when the cooldown ends.
        self._size_save_timer = QTimer(self)
        self._size_save_timer.setSingleShot(True)
        self._size_save_timer.setInterval(300)
        self._size_save_timer.timeout.connect(self._flush_size_save)
        self._size_dirty = False
        #: Monotonic end of the current write cooldown; the timer is only the
        #: live-app flush (a headless caller has no event loop to fire it).
        self._size_cooldown_until = 0.0
        # Appearance is NOT re-applied here: the bootstrap already injected it into
        # RinUI's config before the window existed, and applying a backdrop needs a
        # window handle (RinUI warns and refuses without one). _apply_appearance is
        # for after-the-fact changes, i.e. restore-defaults.
        #
        # The palette, though, can only be read once an application exists: it is
        # what the `system` accent mode reports, so a change to the OS accent has
        # to be followed while that mode is active.
        app = QGuiApplication.instance()
        if app is not None and hasattr(app, "styleHints"):
            # Capture before connecting: the switch below would otherwise emit
            # paletteChanged and re-enter this object.
            self._system_accent.capture()
            app.paletteChanged.connect(self._on_palette_changed)
            app.aboutToQuit.connect(self._flush_size_save)
        self._apply_language()

    def _stage_size(self, key: str, value: int) -> None:
        """Store a size live, coalescing the file write.

        A spin box reports every step. The first write lands immediately (a
        single change is on disk at once, as every setter must be), and further
        steps inside the cooldown are written once when it ends.
        """
        self._store.stage(key, value)
        now = time.monotonic()
        if now < self._size_cooldown_until:
            self._size_dirty = True
            return
        self._store.save()
        self._size_cooldown_until = now + 0.3
        if QCoreApplication.instance() is not None:
            self._size_save_timer.start()

    def _flush_size_save(self, *_args) -> None:
        """Write the last staged size (cooldown end, or application quit)."""
        if QCoreApplication.instance() is not None:
            self._size_save_timer.stop()
        self._size_cooldown_until = 0.0
        if not self._size_dirty:
            return
        self._size_dirty = False
        if not self._store.save():
            # The warning row reads `warning`, which notifies on `changed`.
            self.changed.emit()

    @property
    def _system_accents(self) -> dict:
        """The captured OS accents, owned by ``SystemAccent``.

        Exposed as a view of the capture object rather than a second copy: the
        settings row reads ``light``/``dark`` straight from here (see
        ``_get_accent_os_shading_available``), and the base/variants come from
        the same dict.
        """
        return self._system_accent.accents

    @_system_accents.setter
    def _system_accents(self, accents: dict) -> None:
        self._system_accent.accents = accents

    # --- language ---------------------------------------------------------

    def _get_language(self) -> str:
        """The stored language choice (``system`` or a concrete code)."""
        return str(self._store.get("appearance.language") or "system")

    def _set_language(self, code: str) -> None:
        known = {entry["code"] for entry in self._languages}
        known.add("system")
        if code not in known:
            code = "system"
        if code == self._get_language():
            return
        self._store.set("appearance.language", code)
        self._apply_language()
        self.languageChanged.emit()
        self.changed.emit()

    def _get_languages(self) -> list:
        """Compiled languages; the UI prepends its translated system row."""
        return list(self._languages)

    def _get_system_language_name(self) -> str:
        """The language the `system` choice resolves to, in its own name.

        The picker shows it beside "System default" so the row says what it
        will do; nothing here is translated — language names are shown natively,
        exactly as the other rows do.
        """
        return language_name(resolve_language(SYSTEM_LANGUAGE))

    def _apply_language(self) -> None:
        """Install the selected translation, if a matching ``.qm`` exists.

        A no-op without an application (headless tests). Removing the previous
        translator before installing the next one prevents two catalogues from
        overlapping during a live switch.
        """
        app = QCoreApplication.instance()
        if app is None:
            return
        if self._translator is not None:
            old = self._translator
            app.removeTranslator(old)
            old.deleteLater()
            self._translator = None
        code = resolve_language(self._get_language())
        # English is the source language, but an optional `symplify_en.qm` can
        # override the source copy without editing QML. If it is absent, the
        # source strings are the fallback.
        path = translation_file(self._translation_dir, code)
        if path is not None:
            translator = QTranslator(self)
            if translator.load(str(path)):
                app.installTranslator(translator)
                self._translator = translator
        self._apply_rinui_language(app, code)

    def _apply_rinui_language(self, app: QCoreApplication, code: str) -> None:
        """Install our translations of the RinUI strings this UI shows.

        RinUI's control tooltips and component labels are ``qsTr`` strings too,
        but the library only *ships* ``en_US``/``zh_CN`` and never installs
        them. Depending on those files would leave ``zh_Hant`` users with English
        (RinUI has no Traditional catalogue) and tie us to its package layout;
        instead ``i18n/rinui_<code>.ts`` are hand-maintained fragments covering
        the contexts our UI actually displays (CtrlBtn, ColorPicker,
        NavigationBar, Switch, InfoBar, TextInputMenu). They are compiled by
        ``scripts/update_translations.py`` and selected by the same script/region
        lookup as the app catalogues. A string the fragment does not cover falls
        back to RinUI's English source — degradation is per string, not per
        language, and no RinUI file is read at runtime.
        """
        if self._rinui_translator is not None:
            old = self._rinui_translator
            app.removeTranslator(old)
            old.deleteLater()
            self._rinui_translator = None
        path = translation_file(
            self._translation_dir, code, prefix=RINUI_TRANSLATION_PREFIX
        )
        if path is None:
            return
        translator = QTranslator(self)
        if translator.load(str(path)):
            app.installTranslator(translator)
            self._rinui_translator = translator

    language = Property(str, _get_language, _set_language, notify=languageChanged)
    languages = Property("QVariantList", _get_languages, constant=True)
    systemLanguageName = Property(
        str, _get_system_language_name, constant=True
    )

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
        # Cancel a pending accent write: a pick that settled a moment ago must
        # not fire after the reset and resurrect the colour the user just wiped.
        self._accent_timer.stop()
        self._pending_accent = None
        old_language = self._get_language()
        self._store.reset()
        self._apply_appearance()
        self._apply_language()
        if old_language != self._get_language():
            self.languageChanged.emit()
        self.accentChanged.emit()
        self.latexSizeChanged.emit()
        # The reset touches every group, so every domain announces itself.
        self.appearanceChanged.emit()
        self.fontsChanged.emit()
        self.windowChanged.emit()
        self.keyboardChanged.emit()
        self.configChanged.emit()
        self.changed.emit()

    # --- properties -------------------------------------------------------

    theme = Property(
        str, AppearanceSettings._get_theme, AppearanceSettings._set_theme,
        notify=appearanceChanged,
    )
    backdrop = Property(
        str, AppearanceSettings._get_backdrop, AppearanceSettings._set_backdrop,
        notify=appearanceChanged,
    )
    resultWatermark = Property(
        str, AppearanceSettings._get_result_watermark,
        AppearanceSettings._set_result_watermark, notify=appearanceChanged,
    )
    resultWatermarkPool = Property(
        "QVariantList", AppearanceSettings._get_result_watermark_pool,
        AppearanceSettings._set_result_watermark_pool, notify=appearanceChanged,
    )
    codeTheme = Property(
        str, AppearanceSettings._get_code_theme, AppearanceSettings._set_code_theme,
        notify=appearanceChanged,
    )
    bracketMode = Property(
        str, AppearanceSettings._get_bracket_mode,
        AppearanceSettings._set_bracket_mode, notify=appearanceChanged,
    )
    bracketColors = Property(
        str, AppearanceSettings._get_bracket_colors,
        AppearanceSettings._set_bracket_colors, notify=appearanceChanged,
    )
    # `accent` is the colour in effect (mode resolved) and read-only: the modes
    # above decide it, `customAccent` is the only part the user picks directly.
    accent = Property(str, AppearanceSettings._get_accent, notify=appearanceChanged)
    accentMode = Property(
        str, AppearanceSettings._get_accent_mode,
        AppearanceSettings._set_accent_mode, notify=appearanceChanged,
    )
    accentShading = Property(
        bool, AppearanceSettings._get_accent_shading,
        AppearanceSettings._set_accent_shading, notify=appearanceChanged,
    )
    # Whether the OS's own accents may be used instead of our blend, whether the
    # option exists on this platform at all, and whether it would take effect.
    accentOsShading = Property(
        bool, AppearanceSettings._get_accent_os_shading,
        AppearanceSettings._set_accent_os_shading, notify=appearanceChanged,
    )
    accentOsShadingSupported = Property(
        bool, AppearanceSettings._get_accent_os_shading_supported,
        notify=appearanceChanged,
    )
    accentOsShadingAvailable = Property(
        bool, AppearanceSettings._get_accent_os_shading_available,
        notify=appearanceChanged,
    )
    customAccent = Property(
        str, AppearanceSettings._get_custom_accent,
        AppearanceSettings._set_custom_accent, notify=appearanceChanged,
    )
    # The swatch strip beside the colour control: the WinUI variant family when
    # shading is on, the single flat colour when it is off. Read-only, and it
    # follows the accent in use rather than the stored custom colour.
    accentPreview = Property(
        "QVariantList", AppearanceSettings._get_accent_preview,
        notify=appearanceChanged,
    )
    latexSize = Property(
        int, FontSettings._get_latex_size, FontSettings._set_latex_size,
        notify=fontsChanged,
    )
    # Typography. `*Family` is the preference list the user typed (read back
    # verbatim, so a fallback chain survives an edit); `*FontFamily` is the one
    # family QML can use, resolved to the first installed entry. `latexFontPath`
    # is a font FILE for ziamath, not a family.
    codeFamily = Property(
        str, FontSettings._get_code_family, FontSettings._set_code_family,
        notify=fontsChanged,
    )
    codeFontFamily = Property(
        str, FontSettings._get_code_font_family, notify=fontsChanged
    )
    codeSize = Property(
        int, FontSettings._get_code_size, FontSettings._set_code_size,
        notify=fontsChanged,
    )
    keyboardFamily = Property(
        str, FontSettings._get_keyboard_family, FontSettings._set_keyboard_family,
        notify=fontsChanged,
    )
    keyboardFontFamily = Property(
        str, FontSettings._get_keyboard_font_family, notify=fontsChanged
    )
    # Glyphs that *no* family in the chain can draw ('' = the chain covers them
    # all). Reported per chain, not per family: a gap in the primary face is not
    # a problem when Qt falls back for it — see font_report.missing_glyphs.
    codeMissingGlyphs = Property(
        str, FontSettings._get_code_missing_glyphs, notify=fontsChanged
    )
    keyboardMissingGlyphs = Property(
        str, FontSettings._get_keyboard_missing_glyphs, notify=fontsChanged
    )
    # The fonts themselves, as QFont values carrying the whole family list so Qt
    # performs real per-character fallback. QML's `font` group cannot express a
    # list, so pages bind `font: settingsVM.codeFont` instead of setting a family.
    codeFont = Property(QFont, FontSettings._get_code_font, notify=fontsChanged)
    keyboardFont = Property(
        QFont, FontSettings._get_keyboard_font, notify=fontsChanged
    )
    # How many further installed faces back up the primary one — shown as
    # "fallbacks: N" so the chain is visible without opening the config file.
    codeFallbackCount = Property(
        int, FontSettings._get_code_fallback_count, notify=fontsChanged
    )
    keyboardFallbackCount = Property(
        int, FontSettings._get_keyboard_fallback_count, notify=fontsChanged
    )
    keyboardSize = Property(
        int, FontSettings._get_keyboard_size, FontSettings._set_keyboard_size,
        notify=fontsChanged,
    )
    latexFont = Property(
        str, FontSettings._get_latex_font, FontSettings._set_latex_font,
        notify=fontsChanged,
    )
    latexFontPath = Property(
        str, FontSettings._get_latex_font_path, notify=fontsChanged
    )
    # The family a refused pick named, so the page can say which font it was.
    latexFontError = Property(
        str, FontSettings._get_latex_font_error, notify=latexFontErrorChanged
    )
    # The system fonts that can render math, for the LaTeX font dropdown. Read
    # once per page build (the scan behind it is cached); it only changes when
    # the user installs a font, which a restart picks up.
    mathFonts = Property("QVariantList", FontSettings._get_math_fonts, constant=True)
    rememberWindow = Property(
        bool, WindowSettings._get_remember_window,
        WindowSettings._set_remember_window, notify=windowChanged,
    )
    zenFullscreen = Property(
        bool, WindowSettings._get_zen_fullscreen,
        WindowSettings._set_zen_fullscreen, notify=windowChanged,
    )
    # Read once by MainWindow.qml to size the window at creation (see
    # _restore_geometry for why the size must not be assigned later).
    startupWidth = Property(int, WindowSettings._get_startup_width, constant=True)
    startupHeight = Property(int, WindowSettings._get_startup_height, constant=True)
    configPath = Property(str, _get_config_path, constant=True)
    configMode = Property(str, _get_config_mode, constant=True)
    # `warning` notifies on `changed`, not on `configChanged`: the store raises it
    # from inside a *write*, and every setter emits `changed`, so the row appears
    # the moment a save fails. `configChanged` is the reset's announcement of the
    # config-write status.
    warning = Property(str, _get_warning, notify=changed)
    #: The folder holding user keyboard copies, and the filenames it offers.
    keyboardFolder = Property(
        str, KeyboardSettings._get_keyboard_folder, constant=True
    )
    keyboardLayouts = Property(
        "QVariantList", KeyboardSettings._get_keyboard_layouts,
        notify=keyboardLayoutsChanged,
    )
    keyboardLayout = Property(
        str, KeyboardSettings._get_keyboard_layout,
        KeyboardSettings._set_keyboard_layout, notify=keyboardChanged,
    )
    keyboardError = Property(
        str, KeyboardSettings._get_keyboard_error, notify=keyboardErrorChanged
    )
