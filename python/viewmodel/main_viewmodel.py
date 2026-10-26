"""Root viewmodel for the QML Symplify app.

Aggregates the sub-viewmodels and is exposed to QML as the ``vm``
context property.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QEvent,
    QObject,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QFontMetricsF, QGuiApplication, QKeyEvent

from .. import log_capture
from ..brackets import parse_colors
from ..code_style import Style, theme, to_rich_text
from ..keyboard_config import load_keyboard_layout
from ..latex_render import LatexStyle, render_data_url
from ..model.calculator import Calculator
from ..model.variable import VariableManager
from ..settings import SettingsStore
from .calculator_viewmodel import CalculatorViewModel
from .highlighter import attach
from .history_viewmodel import HistoryModel
from .latex_service import LatexRenderService
from .log_viewmodel import LogViewModel
from .search import HistoryFilterModel, VariablesFilterModel
from .settings_viewmodel import SettingsViewModel
from .variables_viewmodel import VariablesViewModel


class MainViewModel(QObject):
    """Holds the shared models and exposes all sub-viewmodels to QML.

    Signals:
        sendToCode: Requested by the history page to restore a code entry
            in the calculator's Code input. Args: expression (str).
        sendToAssign: Requested by the history page to restore an assign
            entry in the calculator's Assign input. Args:
            name (str), operator (str), expression (str).
    """

    sendToCode = Signal(str)
    sendToAssign = Signal(str, str, str)
    #: `keyboardRevision` changed: LaTeX keycaps must ask for new artwork.
    keyboardStyleChanged = Signal()
    #: The selected custom keyboard file (or the shipped default) changed.
    keyboardTabsChanged = Signal()
    keyboardLoadErrorChanged = Signal()
    keyboardLoadErrorShownChanged = Signal()

    def __init__(
        self,
        settings: SettingsStore,
        theme_manager: QObject | None = None,
        parent: QObject | None = None,
        initial_variables: Mapping[str, Any] | None = None,
        calculation_backend: QObject | None = None,
        translation_dir: Path | None = None,
    ):
        """Initialize all models and viewmodels.

        Args:
            settings: The loaded settings store (single source of truth).
            theme_manager: RinUI's ``ThemeManager``, so the settings viewmodel can
                apply appearance changes; None in headless tests.
            parent: Qt parent.
            initial_variables: Variables a fresh session starts with. The app
                passes ``plotting.plot_variables()`` — ``x`` and ``y`` as
                themselves, so the plotting names are visible in the table and a
                result can use them without defining anything. Left empty here,
                which is what the tests build: the default scope is the
                composition root's decision, not the viewmodel's.
            calculation_backend: How calculation requests leave the UI. None
                keeps the synchronous in-process backend (tests/headless); the
                application passes a ``ProcessBackend`` with a timeout.
            translation_dir: Folder with compiled ``symplify_<code>.qm`` files;
                defaults to the repository's ``i18n/``.
        """
        super().__init__(parent)
        self._calculator = Calculator()
        self._variable_manager = VariableManager()
        for name, value in (initial_variables or {}).items():
            self._variable_manager.save(name, value)

        # One renderer process for both result/variant artwork and history
        # cards. The service owns the cache and invalidates queued work by owner.
        self._latex_service = LatexRenderService(self)
        self._history = HistoryModel(parent=self, latex_service=self._latex_service)
        self._log = LogViewModel(parent=self)
        self._variables_vm = VariablesViewModel(
            self._variable_manager, self._log, self._calculator, parent=self
        )
        self._calculator_vm = CalculatorViewModel(
            self._variable_manager,
            self._history,
            self._log,
            variables_model=self._variables_vm.model,
            parent=self,
            backend=calculation_backend,
            latex_service=self._latex_service,
        )

        # Search-filtered views: the pages bind their views to these, so the
        # source models keep every entry regardless of an active query.
        self._variables_filter = VariablesFilterModel(parent=self)
        self._variables_filter.setSourceModel(self._variables_vm.model)
        self._history_filter = HistoryFilterModel(parent=self)
        self._history_filter.setSourceModel(self._history)

        #: The theme's ink for rendered LaTeX, pushed from QML: the theme colours
        #: are translucent QColors, and turning one into the string the renderer
        #: wants needs the page background behind it (see `MainWindow`), which only
        #: the QML side has.
        self._latex_color = "#000000"
        #: LaTeX keycaps: the same ink, the LaTeX font, but the KEYBOARD size
        #: (not the result size) so they sit at the height of the text keys.
        self._keycap_style: LatexStyle | None = None
        self._keycap_revision = 0
        self._keycap_cache: dict = {}
        #: Attached code highlighters, by their QTextDocument. A theme switch
        #: changes the palette in place instead of rebuilding the page, so the
        #: C++ highlighter needs an explicit recolour (see
        #: `refreshCodeHighlighting`). The document owns the highlighter; the
        #: destroyed hook only drops the dictionary entry.
        self._code_highlighters: dict = {}

        self._settings = SettingsViewModel(
            settings, theme_manager, parent=self, translation_dir=translation_dir
        )
        self._settings.latexSizeChanged.connect(self._apply_latex_style)
        # `changed` rather than a font-specific signal: `latexFontPath` is a
        # filesystem path resolved by `python/fonts.py`, so it is re-read on every
        # settings change rather than only when the family name changes.
        self._settings.changed.connect(self._apply_latex_style)
        self._settings.changed.connect(self._refresh_keyboard_layout)
        self._keyboard_layout = self._settings.keyboardLayout
        self._keyboard_load_error = ""
        self._keyboard_load_error_shown = False
        self._load_keyboard()
        self._apply_latex_style()     # apply the persisted rendering settings now

    def install_log_capture(self) -> None:
        """Take over Qt's and the interpreter's message streams.

        Called by the composition root rather than from ``__init__``: the handlers
        are process-wide and last for the life of the process, so a headless
        ``MainViewModel`` — which is what the tests build — must not hijack them.

        The sink is this viewmodel's log, so whatever Qt or the interpreter says
        lands in the Log page beside the app's own entries.
        """
        log_capture.install(self._log)

    def _apply_latex_style(self) -> None:
        """Hand the assembled `LatexStyle` to every surface that renders LaTeX.

        One place owns it — the ink comes from the theme, the size and the font
        file from the settings store — so the three consumers cannot drift apart.
        Each keeps its own cache, because their policies differ: the calculator
        holds one result, the history renders each entry once, and the details
        panel renders one row and keeps nothing.
        """
        style = LatexStyle(
            color=self._latex_color,
            size=self._settings.latexSize,
            font=self._settings.latexFontPath,
        )
        self._calculator_vm.set_latex_style(style)
        self._history.set_latex_style(style)
        self._variables_filter.set_latex_style(style)

        # Keycaps share the ink and the LaTeX font, but use the keyboard font
        # size: changing the result size must not resize the keyboard, and
        # changing the keyboard size must re-render only the current tab's
        # LaTeX keys. Comparing the frozen style keeps unrelated settings
        # changes from throwing the cache away.
        keycap_style = LatexStyle(
            color=self._latex_color,
            size=self._settings.keyboardSize,
            font=self._settings.latexFontPath,
        )
        if keycap_style != self._keycap_style:
            self._keycap_style = keycap_style
            self._keycap_revision += 1
            self._keycap_cache.clear()
            self.keyboardStyleChanged.emit()

    def _keyboard_layout_path(self) -> Path | None:
        """The chosen custom file, or None for the shipped layout."""
        if not self._keyboard_layout:
            return None
        return Path(self._settings.keyboardFolder) / self._keyboard_layout

    def _load_keyboard(self) -> None:
        self._keyboard_tabs, error = load_keyboard_layout(
            self._keyboard_layout_path()
        )
        self._set_keyboard_load_error(error)

    def _set_keyboard_load_error(self, message: str) -> None:
        """Publish a load failure once; the log/dialog/settings row share it."""
        if message == self._keyboard_load_error:
            return
        self._keyboard_load_error = message
        if message:
            self._keyboard_load_error_shown = False
            self._log.add_error(message, "Keyboard")
        self.keyboardLoadErrorChanged.emit()
        self.keyboardLoadErrorShownChanged.emit()

    def _refresh_keyboard_layout(self) -> None:
        """Reload the QML keyboard model when the selected file changes."""
        name = self._settings.keyboardLayout
        if name == self._keyboard_layout:
            return
        self._keyboard_layout = name
        self._load_keyboard()
        self.keyboardTabsChanged.emit()

    @Slot()
    def reloadKeyboardLayouts(self) -> None:
        """Re-read the current file; the Settings refresh button calls this."""
        self._load_keyboard()
        self.keyboardTabsChanged.emit()

    @Slot()
    def markKeyboardLoadErrorShown(self) -> None:
        if self._keyboard_load_error_shown:
            return
        self._keyboard_load_error_shown = True
        self.keyboardLoadErrorShownChanged.emit()

    @Property("QVariantList", notify=keyboardTabsChanged)
    def keyboardTabs(self) -> list:
        """The active keyboard's tab descriptors, for `KeyboardPanel`."""
        return self._keyboard_tabs

    @Property(str, notify=keyboardLoadErrorChanged)
    def keyboardLoadError(self) -> str:
        return self._keyboard_load_error

    @Property(bool, notify=keyboardLoadErrorShownChanged)
    def keyboardLoadErrorShown(self) -> bool:
        return self._keyboard_load_error_shown

    @Slot(str)
    def set_latex_color(self, color: str) -> None:
        """Set the ink rendered LaTeX is drawn in (called on theme changes).

        The colour is baked into the SVG when it is rendered, so this re-renders
        rather than retinting — which is why nothing renders before this is set:
        `MainWindow` calls it before any page is built.
        """
        qcolor = QColor(color)
        if not qcolor.isValid():
            return
        name = qcolor.name()
        if name == self._latex_color:
            return
        self._latex_color = name
        self._apply_latex_style()

    @Property(int, notify=keyboardStyleChanged)
    def keyboardRevision(self) -> int:
        """Increments when the LaTeX keycap style changes.

        QML bindings pass this value alongside the LaTeX source, which is what
        makes an already-built key ask for fresh artwork after a theme, font or
        keyboard-size change. Pixel data is never mutated in place.
        """
        return self._keycap_revision

    @Slot(str, int, result="QVariantMap")
    def latexKeycap(self, latex: str, revision: int) -> dict:
        """Rendered LaTeX keycap for one key, as ``{url, width, height}``.

        Rendered lazily, only for the visible tab, and cached per revision; an
        empty ``url`` means ziamath refused the source and the QML key falls
        back to its plain ``label``. The size/font are the keycap style built in
        `_apply_latex_style` (LaTeX font, keyboard size), not the result style.
        """
        if not latex:
            return {}
        key = (latex, revision)
        cached = self._keycap_cache.get(key)
        if cached is not None:
            return cached
        url, width, height = render_data_url(latex, self._keycap_style or LatexStyle())
        cached = {"url": url, "width": width, "height": height}
        self._keycap_cache[key] = cached
        return cached

    @Property(QObject, constant=True)
    def calculator(self) -> CalculatorViewModel:
        """The calculator viewmodel."""
        return self._calculator_vm

    @Property(QObject, constant=True)
    def variables(self) -> VariablesViewModel:
        """The variables viewmodel."""
        return self._variables_vm

    @Property(QObject, constant=True)
    def history(self) -> HistoryModel:
        """The history model."""
        return self._history

    @Property(QObject, constant=True)
    def log(self) -> LogViewModel:
        """The log viewmodel."""
        return self._log

    @Property(QObject, constant=True)
    def variablesFilter(self) -> VariablesFilterModel:
        """Search-filtered view of the variables table."""
        return self._variables_filter

    @Property(QObject, constant=True)
    def historyFilter(self) -> HistoryFilterModel:
        """Search-filtered view of the history cards."""
        return self._history_filter

    @Property(QObject, constant=True)
    def settings(self) -> SettingsViewModel:
        """The settings viewmodel (appearance, workspace, window, config path)."""
        return self._settings

    @Slot(str)
    def copyText(self, text: str) -> None:
        """Copy ``text`` to the system clipboard."""
        QGuiApplication.clipboard().setText(text)

    def _palette(self, dark: bool) -> tuple[Mapping[Style, str], tuple[str, ...]]:
        """The code palette and bracket colours every renderer paints with.

        The bracket half is the settings' choice: ``theme`` follows the code
        theme (``code_style.theme``, which itself answers with VS Code's
        registered defaults for the families that name none), and ``custom`` uses
        the user's list. The store keeps that list non-empty — it starts as, and
        is repaired to, the rainbow — and it is the same palette ``color_for``
        falls back to for a palette it is handed none of, so the two agree even
        if one ever arrived empty.
        """
        styles, brackets = theme(self._settings.codeTheme, dark)
        if self._settings.bracketMode == "custom":
            return styles, parse_colors(self._settings.bracketColors)
        return styles, brackets

    @Slot(QObject, bool)
    def attachCodeHighlighting(self, text_document: QObject, dark: bool) -> None:
        """Colour a QML code input (see ``viewmodel/highlighter.py``).

        The page passes the input's ``textDocument`` — a ``QQuickTextDocument``,
        which the annotation here cannot say because Qt's own slot signature for
        a QML argument is ``QObject`` — together with whether the *active* theme
        is dark (RinUI resolves ``Auto`` against the OS, so the page asks it, not
        the setting). The colours then come from the family the settings name
        (``workspace.code_theme``) at that theme: Atom One is One Dark on a dark
        UI and One Light on a light one. The highlighter lives exactly as long as
        the document. A page switch recreates the document and reattaches; a
        *live* theme change does not, so `refreshCodeHighlighting` recolours this
        one in place (and the registry is what finds it again). Names are resolved against the live
        variable scope, so a stored variable is classified apart from a free
        symbol — whether the palette paints that difference is the palette's
        business (Atom One gives both its own foreground).
        """
        styles, bracket_colors = self._palette(dark)
        document = text_document.textDocument()
        highlighter = attach(
            text_document, self._variable_manager.list_all, styles, bracket_colors
        )
        self._code_highlighters[document] = highlighter
        document.destroyed.connect(
            lambda *_: self._code_highlighters.pop(document, None)
        )

    @Slot(bool)
    def refreshCodeHighlighting(self, dark: bool) -> None:
        """Recolour every attached code input for the active theme.

        Called from `MainWindow` on `Theme.currentThemeChanged` (the OS scheme
        change and the settings switch both end there) and on a settings change.
        A page switch used to hide this: RinUI rebuilt the page and the
        highlighter was attached again; a live theme change leaves the document
        (and its old palette) in place.
        """
        styles, bracket_colors = self._palette(dark)
        for document, highlighter in list(self._code_highlighters.items()):
            try:
                highlighter.set_palette(styles, bracket_colors)
            except RuntimeError:
                # The QObject was deleted before its `destroyed` hook ran.
                self._code_highlighters.pop(document, None)

    @Slot(str, bool, result=str)
    def highlighted(self, text: str, dark: bool) -> str:
        """``text`` as markup, for the read-only code labels.

        The same span list the editors are painted from, through the other
        renderer — so a History card and the input it came from agree about what is
        coloured, and there is no second set of rules to keep in step. The page
        passes the active theme, as it does for :meth:`attachCodeHighlighting`.

        The callers are QML *bindings* (a delegate's ``text``), so this runs when a
        row is shown or the theme changes — not once per repaint, and only for the
        rows a view actually has out.

        The scope is resolved here, once: ``to_rich_text`` takes a mapping, where
        the highlighter takes the *provider* so it can ask again on every keystroke.
        """
        styles, bracket_colors = self._palette(dark)
        return to_rich_text(text, self._variable_manager.list_all(), styles, bracket_colors)

    @Slot(str, float, bool, result=str)
    def highlightedElided(self, text: str, width: float, dark: bool) -> str:
        """``text`` elided to ``width`` pixels of the code font, then marked up.

        Qt's ``Text.elide`` is silently ignored for ``Text.RichText`` (probed on
        Qt 6.11: plain and styled text truncate, rich text paints at its full
        width and bleeds over whatever sits beside it), and ``Text.StyledText``
        cannot carry this markup instead — it renders ``&nbsp;`` and ``&lt;``
        literally, so the escaping and the aligned ``=`` padding would break.
        The eliding therefore happens here, on the *plain* string, with the code
        font's metrics — the same font the label paints with — before the span
        list is asked about it. Callers pass their label's width; the elision
        mark itself stays outside every span, so it inherits the label's colour
        rather than the last token's.

        The callers are QML *bindings* on the label's ``text``, so this re-runs
        when the label is resized (a window drag) or the theme changes — the
        same cadence :meth:`highlighted` already had.
        """
        if width <= 0 or not text:
            return ""
        plain = QFontMetricsF(self._settings.codeFont).elidedText(
            text, Qt.TextElideMode.ElideRight, width
        )
        styles, bracket_colors = self._palette(dark)
        # The elision mark stays *outside* the spans, so it inherits the label's
        # own colour instead of the last token's — a truncated number would
        # otherwise end in a pink/red `…` whatever it truncates.
        if plain.endswith("\u2026"):
            body = to_rich_text(plain[:-1], self._variable_manager.list_all(),
                                styles, bracket_colors)
            return body + "\u2026"
        return to_rich_text(plain, self._variable_manager.list_all(), styles, bracket_colors)

    @Slot()
    def focusNext(self) -> None:
        """Move focus to the next control (Ctrl+Tab), using native focus order."""
        self._send_tab(Qt.KeyboardModifier.NoModifier)

    @Slot()
    def focusPrev(self) -> None:
        """Move focus to the previous control (Ctrl+Shift+Tab)."""
        self._send_tab(Qt.KeyboardModifier.ShiftModifier)

    def _send_tab(self, modifiers: Qt.KeyboardModifier) -> None:
        """Synthesize a Tab key press to trigger Qt's native focus navigation.

        This works for any focused control (now and in the future) without
        hard-coding a focus chain, unlike per-control KeyNavigation.
        """
        win = QGuiApplication.focusWindow()
        if win is None:
            tops = QGuiApplication.topLevelWindows()
            win = tops[0] if tops else None
        if win is None:
            return
        press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, modifiers)
        release = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Tab, modifiers)
        QCoreApplication.sendEvent(win, press)
        QCoreApplication.sendEvent(win, release)
