"""Font settings: the three faces, their fallback chains and coverage.

Methods only. The ``Property`` declarations and ``Signal`` objects live on
``SettingsViewModel`` (the QObject subclass), so shiboken registers them; this
module is mixed in and refers to them through ``self``. Every setter here emits
``fontsChanged`` and the catch-all ``changed``.
"""

from PySide6.QtCore import Slot
from PySide6.QtGui import QFont, QGuiApplication

from ..font_report import installed_chain, missing_glyphs
from ..fonts import (
    CODE_GLYPHS,
    expand_keyword,
    math_font_choices,
    math_font_path,
    math_font_typesets,
    split_families,
)
from ..keyboard_config import label_glyphs


class FontSettings:
    """Applies and persists the font group of the user settings."""

    def _get_code_family(self) -> str:
        return self._store.get("workspace.code_family")

    def _set_code_family(self, families: str) -> None:
        self._store.set("workspace.code_family", families)
        self.fontsChanged.emit()
        self.changed.emit()

    def _get_code_size(self) -> int:
        return int(self._store.get("workspace.code_size"))

    def _set_code_size(self, size: int) -> None:
        self._stage_size("workspace.code_size", size)
        self.fontsChanged.emit()
        self.changed.emit()

    def _get_keyboard_family(self) -> str:
        return self._store.get("workspace.keyboard_family")

    def _set_keyboard_family(self, families: str) -> None:
        self._store.set("workspace.keyboard_family", families)
        self.fontsChanged.emit()
        self.changed.emit()

    def _get_keyboard_size(self) -> int:
        return int(self._store.get("workspace.keyboard_size"))

    def _set_keyboard_size(self, size: int) -> None:
        self._stage_size("workspace.keyboard_size", size)
        self.fontsChanged.emit()
        self.changed.emit()

    def _get_latex_font(self) -> str:
        return self._store.get("workspace.latex_font")

    def _set_latex_font(self, family: str) -> None:
        self._store.set("workspace.latex_font", family)
        # `changed` is this property's notify and the signal `MainViewModel`
        # re-assembles the shared `LatexStyle` on, so the emit is what makes a pick
        # take effect: without it the family is stored while every surface goes on
        # rendering the previous font (and the row's own "In use: …" note stays
        # stale) until some unrelated setting happens to move.
        self.fontsChanged.emit()
        self.changed.emit()

    @Slot(str, result=bool)
    def trySetLatexFont(self, family: str) -> bool:
        """Apply ``family``, but only if ziamath can actually typeset with it.

        The scan behind the dropdown is cheap on purpose, so a font whose MATH table
        is present but unreadable can be in it. Proving it costs a real layout, which
        is why it happens here — on the one font the user picked — rather than for
        every candidate. A refusal stores the family for the page's dialog and leaves
        the setting alone.
        """
        if not math_font_typesets(family):
            self._latex_font_error = family
            self.latexFontErrorChanged.emit()
            return False
        self._latex_font_error = ""
        self.latexFontErrorChanged.emit()
        self.latexFont = family
        return True

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
        coverage report walks. See ``font_report.installed_chain``.
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
        return missing_glyphs(self._get_code_family(), CODE_GLYPHS)

    def _get_keyboard_missing_glyphs(self) -> str:
        """Glyphs no family in the keyboard chain can draw.

        Measured against the glyphs the layout actually shows
        (`keyboard_config.label_glyphs`), which is the only place a missing
        character would be visible.
        """
        return missing_glyphs(
            self._get_keyboard_family(), label_glyphs(self._keyboard_layout_path())
        )

    def _get_latex_font_error(self) -> str:
        return self._latex_font_error

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

    def _get_latex_size(self) -> int:
        return int(self._store.get("workspace.latex_size"))

    def _set_latex_size(self, size: int) -> None:
        self._stage_size("workspace.latex_size", size)
        self.latexSizeChanged.emit()
        self.fontsChanged.emit()
        self.changed.emit()
