"""Appearance settings: theme, backdrop, accent, code colours and watermarks.

Methods only. The ``Property`` declarations, the ``Signal`` objects and the
shared state live on ``SettingsViewModel`` (the QObject subclass), so shiboken
registers them; this module is mixed in and refers to them through ``self``.
Every setter here emits ``appearanceChanged`` and the catch-all ``changed``.
"""

import sys

from PySide6.QtCore import Slot
from PySide6.QtGui import QColor

from ..accent import for_scheme, variants
from ..code_style import surface as code_surface
from ..code_themes import label as family_label
from ..settings import DEFAULTS


class AppearanceSettings:
    """Applies and persists the appearance group of the user settings."""

    # --- watermark --------------------------------------------------------

    def _get_result_watermark(self) -> str:
        """The empty result pane's watermark: 'icon' (default) or 'random'."""
        return str(self._store.get("workspace.result_watermark") or "icon")

    def _get_result_watermark_pool(self) -> list:
        """The random watermark's LaTeX pool; the store validates and ships it."""
        pool = self._store.get("workspace.result_watermark_pool")
        return list(pool) if isinstance(pool, (list, tuple)) else []

    def _set_result_watermark(self, kind: str) -> None:
        """Write the watermark kind through the store (and persist + notify)."""
        self._store.set("workspace.result_watermark", kind)
        # PySide does not emit the NOTIFY signal for a Python-side write, and
        # every consumer (the calc VM's re-roll, the QML source switch) hangs
        # off ``changed`` rather than off a property read, so emit it here.
        self.appearanceChanged.emit()
        self.changed.emit()

    def _set_result_watermark_pool(self, items: object) -> None:
        """Write the watermark pool through the store.

        No coercion here: a string would silently explode into its characters,
        and the store's own validator owns the list-only contract.
        """
        self._store.set("workspace.result_watermark_pool", items)
        self.appearanceChanged.emit()
        self.changed.emit()

    # --- theme and backdrop ----------------------------------------------

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
        self.appearanceChanged.emit()
        self.changed.emit()

    def _get_backdrop(self) -> str:
        return self._store.get("appearance.backdrop")

    def _set_backdrop(self, backdrop: str) -> None:
        backdrop = self._store.set("appearance.backdrop", backdrop)
        if self._theme_manager is not None:
            self._theme_manager.apply_backdrop_effect(backdrop)
        self.appearanceChanged.emit()
        self.changed.emit()

    # --- accent -----------------------------------------------------------

    def _get_accent_mode(self) -> str:
        """Which accent the UI uses: ``default`` / ``system`` / ``custom``."""
        return self._store.get("appearance.accent_mode")

    def _set_accent_mode(self, mode: str) -> None:
        self._store.set("appearance.accent_mode", mode)
        # Switching Default/System/Custom changes the colour in effect even when
        # no picker moved, so the QML accent handler has to run for this too.
        self.accentChanged.emit()
        self.appearanceChanged.emit()
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
        self.appearanceChanged.emit()
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
            return self._system_accent.base(DEFAULTS["appearance"]["accent"])
        if mode == "custom":
            return self._get_custom_accent()
        return DEFAULTS["appearance"]["accent"]

    @Slot(bool, result=str)
    def accentForScheme(self, dark: bool) -> str:
        """The accent to apply for a theme of the given lightness.

        ``default`` and ``custom`` are colours the OS knows nothing about, so they
        take the derivation (``for_scheme``: the shell's own shade for the scheme
        — the darker ``dark1`` on light, the lighter ``light2`` on dark) — the
        same on every platform. ``system`` on Windows uses the value the OS
        reports for the scheme instead: our derivation reproduces the shell's ramp
        to within a unit, but the shell is the one that wrote it, so its own value
        wins when the OS-shading option is on; with it off, ``system`` derives
        like everything else.

        Shading off means no per-scheme finetuning at all: the base verbatim.
        """
        base = self._get_accent()
        if not self._get_accent_shading():
            return base
        if self._get_accent_mode() == "system":
            from_os = self._system_accent.scheme(
                bool(dark), self._get_accent_os_shading()
            )
            if from_os:
                return from_os
        return for_scheme(base, bool(dark))

    def _get_accent_preview(self) -> list:
        """The swatches the settings page shows beside the colour control.

        A preview, not a control: it follows the accent the UI is using (not the
        stored custom colour the dropdown next to it edits), and it shows the
        palette actually in play — the OS's dark/base/light trio in ``system``
        mode on Windows, our derived trio otherwise, and a single flat swatch
        when shading is off.
        """
        base = self._get_accent()
        if not self._get_accent_shading():
            return [base]
        if self._get_accent_mode() == "system" and self._get_accent_os_shading():
            dark = self._system_accent.scheme(True, True)
            light = self._system_accent.scheme(False, True)
            if dark and light:
                return [light, base, dark]      # darkest to lightest
        return list(variants(base))

    def _on_palette_changed(self, *_) -> None:
        """Follow the OS accent while the ``system`` mode is active."""
        self._system_accent.capture()
        if self._get_accent_mode() == "system":
            self.accentChanged.emit()
            self.changed.emit()

    def _get_accent_shading(self) -> bool:
        return bool(self._store.get("appearance.accent_shading"))

    def _set_accent_shading(self, enabled: bool) -> None:
        """Toggle the WinUI-style per-scheme finetuning of the accent."""
        self._store.set("appearance.accent_shading", bool(enabled))
        # The applied colour changes with it, so announce the accent too.
        self.accentChanged.emit()
        self.appearanceChanged.emit()
        self.changed.emit()

    def _get_accent_os_shading(self) -> bool:
        return bool(self._store.get("appearance.accent_os_shading"))

    def _set_accent_os_shading(self, enabled: bool) -> None:
        """Prefer the OS's own per-scheme accent over our blend."""
        self._store.set("appearance.accent_os_shading", bool(enabled))
        self.accentChanged.emit()
        self.appearanceChanged.emit()
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

        The captured values are read straight out of ``self._system_accents`` and
        never through ``SystemAccent.scheme``: that one answers ``""`` while
        this very option is *off* — it is where the opt-out lives — so asking it
        here made the row's availability depend on the switch already being on.
        Turning the option off disabled the row that turns it back on, and the
        option became one-way.
        """
        if not self._get_accent_os_shading_supported():
            return False
        if self._get_accent_mode() != "system":
            return False
        if not self._get_accent_shading():
            return False
        return bool(self._system_accents.get("light") and self._system_accents.get("dark"))

    # --- code theme -------------------------------------------------------

    def _get_code_theme(self) -> str:
        return self._store.get("workspace.code_theme")

    def _set_code_theme(self, family: str) -> None:
        self._store.set("workspace.code_theme", family)
        self.appearanceChanged.emit()
        self.changed.emit()

    @Slot(str, result=str)
    def codeThemeLabel(self, family: str) -> str:
        """A family's display name.

        The ids and their labels live in ``python/code_themes.py``, so the page
        does not repeat them — it only lists which id each row sets.
        """
        return family_label(family)

    @Slot(bool, result="QVariantMap")
    def codeSurface(self, dark: bool) -> dict[str, str]:
        """The code theme's ``background``, ``ink`` and ``placeholder`` for a code input.

        The page passes the *effective* theme, as it does for the highlighter
        (RinUI resolves ``Auto``, so the setting is not the authority). An empty
        value means the family has no opinion on that part and the control keeps
        the UI theme's own colour.
        """
        background, ink, placeholder = code_surface(self._store.get("workspace.code_theme"), dark)
        return {"background": background, "ink": ink, "placeholder": placeholder}

    # --- brackets ---------------------------------------------------------

    def _get_indent_rainbow(self) -> bool:
        """Tint every indentation level in the code inputs."""
        return bool(self._store.get("workspace.indent_rainbow"))

    def _set_indent_rainbow(self, enabled: bool) -> None:
        if bool(enabled) == self._get_indent_rainbow():
            return
        self._store.set("workspace.indent_rainbow", bool(enabled))
        self.appearanceChanged.emit()
        self.changed.emit()

    def _get_bracket_mode(self) -> str:
        return self._store.get("workspace.bracket_mode")

    def _set_bracket_mode(self, mode: str) -> None:
        if mode == self._get_bracket_mode():
            return
        self._store.set("workspace.bracket_mode", mode)
        self.appearanceChanged.emit()
        self.changed.emit()

    def _get_bracket_colors(self) -> str:
        """The custom palette, as stored (normalised by the store)."""
        return self._store.get("workspace.bracket_colors")

    def _set_bracket_colors(self, colors: str) -> None:
        """Store a custom palette; unusable entries are dropped, not rejected.

        The field binds back to this, so what it shows after a commit is what
        will actually be painted.
        """
        if colors == self._get_bracket_colors():
            return
        self._store.set("workspace.bracket_colors", colors)
        self.appearanceChanged.emit()
        self.changed.emit()
