# coding: utf-8
"""Root viewmodel for the QML Symplify app.

Aggregates the sub-viewmodels and is exposed to QML as the ``vm``
context property.
"""

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QEvent,
    QObject,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QFontMetricsF, QGuiApplication, QKeyEvent
from typing import Optional

from .. import log_capture
from ..code_style import to_rich_text, theme
from ..model.calculator import Calculator
from ..model.variable import VariableManager
from ..settings import SettingsStore
from .calculator_viewmodel import CalculatorViewModel
from .history_viewmodel import HistoryModel
from .log_viewmodel import LogViewModel
from .highlighter import attach
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

    def __init__(
        self,
        settings: SettingsStore,
        theme_manager: Optional[QObject] = None,
        parent: Optional[QObject] = None,
    ):
        """Initialize all models and viewmodels.

        Args:
            settings: The loaded settings store (single source of truth).
            theme_manager: RinUI's ``ThemeManager``, so the settings viewmodel can
                apply appearance changes; None in headless tests.
        """
        super().__init__(parent)
        self._calculator = Calculator()
        self._variable_manager = VariableManager()

        self._history = HistoryModel(parent=self)
        self._log = LogViewModel(parent=self)
        self._variables_vm = VariablesViewModel(
            self._variable_manager, self._log, self._calculator, parent=self
        )
        self._calculator_vm = CalculatorViewModel(
            self._calculator,
            self._variable_manager,
            self._history,
            self._log,
            variables_model=self._variables_vm.model,
            parent=self,
        )

        # Search-filtered views: the pages bind their views to these, so the
        # source models keep every entry regardless of an active query.
        self._variables_filter = VariablesFilterModel(parent=self)
        self._variables_filter.setSourceModel(self._variables_vm.model)
        self._history_filter = HistoryFilterModel(parent=self)
        self._history_filter.setSourceModel(self._history)

        self._settings = SettingsViewModel(settings, theme_manager, parent=self)
        self._settings.latexSizeChanged.connect(self._apply_latex_size)
        self._apply_latex_size()      # apply the persisted rendering settings now
        self._settings.changed.connect(self._apply_latex_font)
        self._apply_latex_font()

    def install_log_capture(self) -> None:
        """Take over Qt's and the interpreter's message streams.

        Called by the composition root rather than from ``__init__``: the handlers
        are process-wide and last for the life of the process, so a headless
        ``MainViewModel`` — which is what the tests build — must not hijack them.

        The sink is this viewmodel's log, so whatever Qt or the interpreter says
        lands in the Log page beside the app's own entries.
        """
        log_capture.install(self._log)

    def _apply_latex_size(self) -> None:
        """Push the configured result font size to everything that renders LaTeX."""
        size = self._settings.latexSize
        self._calculator_vm.set_latex_size(size)
        self._history.set_latex_size(size)

    def _apply_latex_font(self) -> None:
        """Push the configured LaTeX font file to everything that renders LaTeX.

        ``latexFontPath`` is a filesystem path (resolved by ``python/fonts.py``),
        so it is re-read on every settings change rather than only when the
        family name changes.
        """
        path = self._settings.latexFontPath
        self._calculator_vm.set_latex_font(path)
        self._history.set_latex_font(path)

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
        """The settings viewmodel (appearance, rendering, window, config path)."""
        return self._settings

    @Slot(str)
    def copyText(self, text: str) -> None:
        """Copy ``text`` to the system clipboard."""
        QGuiApplication.clipboard().setText(text)

    @Slot(QObject, bool)
    def attachCodeHighlighting(self, text_document: QObject, dark: bool) -> None:
        """Colour a QML code input (see ``viewmodel/highlighter.py``).

        The page passes the input's ``textDocument`` — a ``QQuickTextDocument``,
        which the annotation here cannot say because Qt's own slot signature for
        a QML argument is ``QObject`` — together with whether the *active* theme
        is dark (RinUI resolves ``Auto`` against the OS, so the page asks it, not
        the setting). The colours then come from the family the settings name
        (``appearance.code_theme``) at that theme: Atom One is One Dark on a dark
        UI and One Light on a light one. The highlighter lives exactly as long as
        the document, which RinUI recreates with the page — which is also what
        re-applies a changed theme or family. Names are resolved against the live
        variable scope, so a stored variable is classified apart from a free
        symbol — whether the palette paints that difference is the palette's
        business (Atom One gives both its own foreground).
        """
        styles, bracket_colors = theme(self._settings.codeTheme, dark)
        attach(text_document, self._variable_manager.list_all, styles, bracket_colors)

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
        styles, bracket_colors = theme(self._settings.codeTheme, dark)
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
        styles, bracket_colors = theme(self._settings.codeTheme, dark)
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
