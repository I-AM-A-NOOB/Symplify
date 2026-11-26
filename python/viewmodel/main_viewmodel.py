"""Root viewmodel for the QML Symplify app.

Aggregates the sub-viewmodels and is exposed to QML as the ``vm``
context property.
"""

import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Q_ARG,
    Property,
    QCoreApplication,
    QEvent,
    QMetaObject,
    QObject,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QFontMetricsF,
    QGuiApplication,
    QKeyEvent,
    QTextCursor,
)

from .. import log_capture
from ..brackets import parse_colors
from ..code_style import Style, theme, to_rich_text
from ..editing import apply as apply_edit
from ..keyboard_config import load_keyboard_layout
from ..latex_render import LatexStyle
from ..settings import SettingsStore
from ..store_client import StoreClient
from .calculator_viewmodel import CalculatorViewModel
from .highlighter import attach
from .history_viewmodel import HistoryModel, HistoryWindowModel
from .latex_jobs import LatexJobs
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
    #: Restore the canonical result text instead of the original input, for a
    #: result whose source text no longer parses under the current policy.
    #: Args: mode, name, result.
    sendToResult = Signal(str, str, str)
    #: Restore the canonical input text (syntax normalized, still unevaluated).
    #: Args: mode, name, operator, canonical expression.
    sendToCanonical = Signal(str, str, str, str)
    #: `keyboardRevision` changed: LaTeX keycaps must ask for new artwork.
    keyboardStyleChanged = Signal()
    #: A batch of keycap artwork arrived (a QML binding dependency: the cache
    #: changed without any property the binding already named).
    keycapArtChanged = Signal()
    #: The selected custom keyboard file (or the shipped default) changed.
    keyboardTabsChanged = Signal()
    keyboardLoadErrorChanged = Signal()
    keyboardLoadErrorShownChanged = Signal()
    #: The calculator's focused, chrome-less reading mode changed.
    zenModeChanged = Signal()

    def __init__(
        self,
        settings: SettingsStore,
        theme_manager: QObject | None = None,
        parent: QObject | None = None,
        initial_variables: Mapping[str, Any] | None = None,
        calculation_backend: QObject | None = None,
        variables_backend: QObject | None = None,
        store_client: StoreClient | None = None,
        translation_dir: Path | None = None,
        icon_dir: Path | None = None,
        history_path: Path | None = None,
    ):
        """Initialize all models and viewmodels.

        Args:
            settings: The loaded settings store (single source of truth).
            theme_manager: RinUI's ``ThemeManager``, so the settings viewmodel can
                apply appearance changes; None in headless tests.
            parent: Qt parent.
            initial_variables: Variables a fresh session starts with **on the legacy
                test/headless path**. The app seeds the Store instead
                (``StoreClient.bootstrap(plotting_seeds())``), so this mapping is
                ignored when ``store_client`` is supplied.
            calculation_backend: How calculation requests leave the UI. None
                keeps the synchronous in-process backend (tests/headless); the
                application passes a ``ProcessBackend`` with a timeout.
            variables_backend: The dedicated worker for the Variables page's
                add/update writes. None keeps those writes in-process
                (tests/headless); the application passes a second
                ``ProcessBackend`` so variable edits also have a deadline and
                never run on the UI thread.
            store_client: The application's Store worker client. When present,
                the Variables table reads Store entries, the Calculator's scope
                is the Store snapshot, and writes commit StoreEntryCandidate
                values; ``VariableManager`` is not created.
            translation_dir: Folder with compiled ``symplify_<code>.qm`` files
                (and the ``rinui_<code>.qm`` fragments); defaults to the
                repository's ``i18n/``.
            icon_dir: Folder holding ``Symplify_mono.svg``, the markup the icon
                watermark is built from; defaults to the ``icon/`` folder beside
                the resolved translation folder (``ROOT/icon`` both in a
                checkout and next to the frozen exe).
            history_path: Optional ``history.json``. The app passes the file
                beside ``config.yaml``; tests/headless callers leave it None.
        """
        super().__init__(parent)
        self._calculator: Any | None = None
        self._variable_manager: Any | None = None
        if store_client is None:
            from ..model.calculator import Calculator
            from ..model.variable import VariableManager

            self._calculator = Calculator()
            self._variable_manager = VariableManager()
            for name, value in (initial_variables or {}).items():
                self._variable_manager.save(name, value)

        # One renderer process for both result/variant artwork and history
        # cards. The service owns the cache and invalidates queued work by owner.
        self._latex_service = LatexRenderService(self)
        self._history = HistoryModel(
            parent=self, latex_service=self._latex_service, path=history_path
        )
        self._log = LogViewModel(parent=self)
        if self._history.load_error:
            self._log.add_warning(self._history.load_error, "History")
        self._variables_vm = VariablesViewModel(
            self._variable_manager,
            self._log,
            self._calculator,
            backend=variables_backend,
            store=store_client,
            parent=self,
        )
        self._calculator_vm = CalculatorViewModel(
            self._variable_manager,
            self._history,
            self._log,
            variables_model=self._variables_vm.model,
            parent=self,
            backend=calculation_backend,
            latex_service=self._latex_service,
            icon_svg=self._read_watermark_svg(icon_dir, translation_dir),
            scope_source=(
                self._variables_vm.scope_for
                if store_client is not None else None
            ),
        )

        # Search-filtered views: the pages bind their views to these, so the
        # source models keep every entry regardless of an active query.
        self._variables_filter = VariablesFilterModel(parent=self)
        self._variables_filter.setSourceModel(self._variables_vm.model)
        self._variables_vm.attach_filter(self._variables_filter)
        self._history_filter = HistoryFilterModel(parent=self)
        self._history_filter.setSourceModel(self._history)
        #: The revealed slice of the filtered history; the page's `Repeater`
        #: builds one card per row, so this is what keeps a long history from
        #: building every card when the page opens.
        self._history_window = HistoryWindowModel(parent=self)
        self._history_window.setSourceModel(self._history_filter)

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
        #: Keycap artwork is rendered by the shared renderer process: the QML
        #: binding asks for a key and gets a cache hit or `{}` (the plain label),
        #: and `keycapArtRevision` re-evaluates it once a batch has arrived.
        self._keycap_jobs = LatexJobs(self._latex_service, "keycaps", self)
        self._keycap_jobs.rendered.connect(self._on_keycap_rendered)
        self._keycap_jobs.failed.connect(self._on_keycap_failed)
        self._keycap_pending: set[tuple[str, int]] = set()
        self._keycap_art_revision = 0
        self._keycap_art_timer = QTimer(self)
        self._keycap_art_timer.setSingleShot(True)
        self._keycap_art_timer.setInterval(16)
        self._keycap_art_timer.timeout.connect(self._flush_keycap_art)
        #: A size/font burst: the first change applies at once, later steps only
        #: move the style, and one artwork refresh runs when the cooldown ends.
        self._style_timer = QTimer(self)
        self._style_timer.setSingleShot(True)
        self._style_timer.setInterval(180)
        self._style_timer.timeout.connect(self._flush_latex_style)
        self._style_pending = False
        #: Monotonic end of the current burst window; the timer is the live-app
        #: flush (a headless caller calls `_flush_latex_style` itself).
        self._style_cooldown_until = 0.0
        #: The `LatexStyle` currently handed to the renderers (the last one built).
        self._active_latex_style: LatexStyle | None = None
        #: Attached code highlighters, by their QTextDocument. A theme switch
        #: changes the palette in place instead of rebuilding the page, so the
        #: C++ highlighter needs an explicit recolour (see
        #: `refreshCodeHighlighting`). The document owns the highlighter; the
        #: destroyed hook only drops the dictionary entry.
        self._code_highlighters: dict = {}
        #: Rich-text markup memo for the read-only labels: `(plain text, dark,
        #: scope revision) -> markup`. A table cell's binding is re-evaluated on
        #: every resize frame while the details panel animates, and each call used
        #: to re-tokenize the same text and rebuild the same palette dict. Cleared
        #: by `_invalidate_scope` (a variable moved) and by any appearance change.
        self._markup_cache: dict[tuple, str] = {}
        self._scope_revision = 0
        #: The palette is two dicts built per code family; the same pair is asked
        #: for by every cell and every card, so it is kept per theme side until an
        #: appearance setting moves.
        self._palette_cache: dict[bool, tuple] = {}
        #: The code font's metrics, built once per font change: constructing it per
        #: cell per frame was the largest part of the elided-label cost.
        self._code_font_metrics: QFontMetricsF | None = None

        self._settings = SettingsViewModel(
            settings, theme_manager, parent=self, translation_dir=translation_dir
        )
        # Fonts: the assembled `LatexStyle` is re-read when a face or its size
        # changes (the path is resolved from the font name, so it moves with it).
        self._settings.fontsChanged.connect(self._on_fonts_changed)
        # The watermark's kind and pool are appearance; the keyboard selection
        # reloads the layout model on its own channel. Neither needs a window
        # resize or an unrelated setting to have moved.
        self._settings.appearanceChanged.connect(self._apply_watermark)
        self._settings.appearanceChanged.connect(self._invalidate_palette)
        self._settings.keyboardChanged.connect(self._refresh_keyboard_layout)
        self._settings.parseSettingsChanged.connect(self._apply_parse_policy)
        #: Any variable write changes what a name resolves to, so the markup memo
        #: and the highlighters' scope provider must see the new snapshot.
        model = self._variables_vm.model
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset,
                       model.dataChanged, model.layoutChanged):
            signal.connect(self._invalidate_scope)
        self._keyboard_layout = self._settings.keyboardLayout
        self._zen_mode = False
        self._keyboard_load_error = ""
        self._keyboard_load_error_shown = False
        self._load_keyboard()
        self._apply_latex_style()     # apply the persisted rendering settings now
        self._apply_watermark()       # and the empty-state watermark's kind/pool
        self._apply_parse_policy()    # and the persisted parser switches

    def _apply_parse_policy(self) -> None:
        """Push the current parser policy into both calculation viewmodels.

        The policy is also what the code inputs paint with (a disabled ``!`` or
        juxtaposition), so the attached highlighters recompute in place and the
        read-only markup memo is dropped. Pages rebuild on navigation, which is
        what re-renders their labels; the live editors are the ones a switch can
        be seen on while the Settings page is open.
        """
        policy = self._settings.parse_policy()
        self._calculator_vm.set_parse_policy(policy)
        self._variables_vm.set_parse_policy(policy)
        self._markup_cache.clear()
        for document, highlighter in list(self._code_highlighters.items()):
            try:
                highlighter.refresh()
            except RuntimeError:
                # The QObject was deleted before its `destroyed` hook ran.
                self._code_highlighters.pop(document, None)

    def install_log_capture(self) -> None:
        """Take over Qt's and the interpreter's message streams.

        Called by the composition root rather than from ``__init__``: the handlers
        are process-wide and last for the life of the process, so a headless
        ``MainViewModel`` — which is what the tests build — must not hijack them.

        The sink is this viewmodel's log, so whatever Qt or the interpreter says
        lands in the Log page beside the app's own entries.
        """
        log_capture.install(self._log)

    def _read_watermark_svg(
        self, icon_dir: Path | None, translation_dir: Path | None
    ) -> str:
        """Read the monogram markup the icon watermark tints, or `""`.

        Absent artwork is not an error: the pane then simply draws nothing for
        the icon kind, while the random kind keeps working. Only when neither
        folder is given does the repository layout supply the path, which is what
        headless tests and the composition root's default both hit.
        """
        if icon_dir is not None:
            folder = Path(icon_dir)
        else:
            base = (Path(translation_dir) if translation_dir is not None
                    else Path(__file__).resolve().parents[2] / "i18n")
            folder = base.resolve().parent / "icon"
        try:
            return (folder / "Symplify_mono.svg").read_text(encoding="utf-8")
        except OSError:
            return ""

    def _apply_watermark(self) -> None:
        """Hand the empty-result watermark's kind and pool to the calculator.

        The settings viewmodel reads and validates the store; the calculator
        viewmodel owns the empty state and the render, and re-renders on its own
        whenever the LaTeX style changes.
        """
        self._calculator_vm.set_watermark(
            self._settings.resultWatermark, self._settings.resultWatermarkPool
        )

    def _apply_latex_style(self, rerender: bool = True) -> bool:
        """Hand the assembled `LatexStyle` to every surface that renders LaTeX.

        One place owns it — the ink comes from the theme, the size and the font
        file from the settings store — so the three consumers cannot drift apart.
        Each keeps its own cache, because their policies differ: the calculator
        holds one result, the history renders each entry once, and the details
        panel renders one row and keeps nothing.

        Returns True when the *LaTeX* style actually moved (a code-font change
        emits `fontsChanged` too, and must not re-render every formula). The
        keycap style is checked independently: its size can change without the
        result style changing.
        """
        # The code font's metrics belong to the same font settings; the elided
        # labels are the only consumer, and they must not keep the old face.
        self._code_font_metrics = None
        style = LatexStyle(
            color=self._latex_color,
            size=self._settings.latexSize,
            font=self._settings.latexFontPath,
        )
        changed = style != self._active_latex_style
        self._active_latex_style = style
        if changed:
            self._calculator_vm.set_latex_style(style, rerender=rerender)
            self._history.set_latex_style(style, invalidate=rerender)
            self._variables_vm.set_latex_style(style)

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
            self._keycap_jobs.reset()
            self._keycap_pending.clear()
            self._keycap_cache.clear()
            self.keyboardStyleChanged.emit()
        return changed

    def _on_fonts_changed(self) -> None:
        """Apply a font/size change now; coalesce a burst's re-render.

        A single change (one pick, one size) must be visible at once; a spin
        box's steps within the cooldown only move the style, and one refresh
        runs when it ends. A change that does not move the LaTeX style (a code
        font family, say) returns False and schedules nothing.
        """
        burst = time.monotonic() < self._style_cooldown_until
        changed = self._apply_latex_style(rerender=not burst)
        if not changed:
            return
        if burst:
            self._style_pending = True
            return
        self._style_cooldown_until = time.monotonic() + 0.18
        if QCoreApplication.instance() is not None:
            self._style_timer.start()

    def _flush_latex_style(self) -> None:
        """Re-render the result and history once, at the end of a burst."""
        if QCoreApplication.instance() is not None:
            self._style_timer.stop()
        self._style_cooldown_until = 0.0
        if not self._style_pending:
            return
        self._style_pending = False
        self._calculator_vm.refresh_latex_artwork()
        self._history.refresh_latex_artwork()

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

    def _set_zen_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._zen_mode:
            return
        self._zen_mode = enabled
        self.zenModeChanged.emit()

    @Slot()
    def toggleZen(self) -> None:
        """Enter or leave the calculator's focused result/plot view."""
        self._set_zen_mode(not self._zen_mode)

    @Slot(bool)
    def setZenMode(self, enabled: bool) -> None:
        self._set_zen_mode(enabled)

    @Property(bool, notify=zenModeChanged)
    def zenMode(self) -> bool:
        return self._zen_mode

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

    @Property(int, notify=keycapArtChanged)
    def keycapArtRevision(self) -> int:
        """Bumped when a batch of keycap artwork arrived.

        The cache is not a QML property, so this is the dependency the key grid
        names to re-read it; completions are coalesced into one bump per 16 ms.
        """
        return self._keycap_art_revision

    @Slot(str, int, result="QVariantMap")
    def latexKeycap(self, latex: str, revision: int) -> dict:
        """Keycap artwork for one key, as ``{url, width, height}``.

        Asynchronous: the first call asks the shared renderer and answers ``{}``
        so QML draws the plain ``label``; `keycapArtRevision` re-evaluates the
        binding when the batch lands. With no QCoreApplication the service
        renders inline, and the cache is filled before this method returns, so
        headless callers get the artwork on the first call.

        An empty ``url`` means ziamath refused the source, and the QML key falls
        back to its label. The size/font are the keycap style built in
        `_apply_latex_style` (LaTeX font, keyboard size), not the result style.
        """
        if not latex:
            return {}
        key = (latex, revision)
        cached = self._keycap_cache.get(key)
        if cached is not None:
            return cached
        if key not in self._keycap_pending:
            self._keycap_pending.add(key)
            self._keycap_jobs.request(
                key, latex, self._keycap_style or LatexStyle()
            )
        cached = self._keycap_cache.get(key)
        if cached is not None:
            return cached
        # Not rendered yet: the same shape as a refused source, so QML's
        # `cap.url === ""` fallback and its Image.source stay well-typed.
        return {"url": "", "width": 0, "height": 0}

    def _on_keycap_rendered(
        self, target: tuple[str, int], url: str, width: int, height: int
    ) -> None:
        self._keycap_pending.discard(target)
        self._keycap_cache[target] = {
            "url": url, "width": width, "height": height,
        }
        self._schedule_keycap_art()

    def _on_keycap_failed(self, target: tuple[str, int], message: str) -> None:
        self._keycap_pending.discard(target)
        self._keycap_cache[target] = {"url": "", "width": 0, "height": 0}
        self._log.add_warning(f"LaTeX keycap render failed: {message}", "Keyboard")
        self._schedule_keycap_art()

    def _schedule_keycap_art(self) -> None:
        if (QCoreApplication.instance() is not None
                and not self._keycap_art_timer.isActive()):
            self._keycap_art_timer.start()

    def _flush_keycap_art(self) -> None:
        self._keycap_art_revision += 1
        self.keycapArtChanged.emit()

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
    def historyWindow(self) -> HistoryWindowModel:
        """The revealed slice of the filtered history (the page's card model)."""
        return self._history_window

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
        cached = self._palette_cache.get(dark)
        if cached is not None:
            return cached
        styles, brackets = theme(self._settings.codeTheme, dark)
        if self._settings.bracketMode == "custom":
            brackets = parse_colors(self._settings.bracketColors)
        self._palette_cache[dark] = (styles, brackets)
        return styles, brackets

    def _code_scope(self) -> dict[str, Any]:
        """Names only, for the lexer: values are irrelevant to colouring."""
        if self._variable_manager is not None:
            return self._variable_manager.list_all()
        return {name: True for name in self._variables_vm.model.names()}

    def _invalidate_scope(self, *_args) -> None:
        """A variable was written: markup classified names against the old scope."""
        self._scope_revision += 1
        self._markup_cache.clear()

    def _invalidate_palette(self, *_args) -> None:
        """An appearance setting moved: the palette and every markup it painted."""
        self._palette_cache.clear()
        self._markup_cache.clear()

    def _code_metrics(self) -> QFontMetricsF:
        """The code font's metrics, built once per font change."""
        if self._code_font_metrics is None:
            self._code_font_metrics = QFontMetricsF(self._settings.codeFont)
        return self._code_font_metrics

    def _markup(self, text: str, dark: bool) -> str:
        """``text`` as markup, memoized by text, theme side, scope and policy.

        The parser switches are part of the key because they change whether a
        juxtaposition or a standalone ``!`` is painted as invalid: two custom
        policies share ``profile_id``, so the policy itself is the key.
        """
        policy = self._settings.parse_policy()
        key = (text, dark, self._scope_revision, policy)
        cached = self._markup_cache.get(key)
        if cached is not None:
            return cached
        styles, bracket_colors = self._palette(dark)
        markup = to_rich_text(
            text, self._code_scope(), styles, bracket_colors, policy
        )
        if len(self._markup_cache) >= 512:
            self._markup_cache.clear()
        self._markup_cache[key] = markup
        return markup

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
            text_document,
            self._code_scope,
            styles,
            bracket_colors,
            policy_provider=self._settings.parse_policy,
            indent_rainbow=self._settings.indentRainbow,
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
                highlighter.set_indent_rainbow(self._settings.indentRainbow)
                if not highlighter.set_palette(styles, bracket_colors):
                    # Same palette, but the parser policy or the indent switch
                    # may have moved: both paint without a theme change.
                    highlighter.refresh()
            except RuntimeError:
                # The QObject was deleted before its `destroyed` hook ran.
                self._code_highlighters.pop(document, None)

    @Slot(QObject)
    def refreshBracketMatch(self, editor: QObject) -> None:
        """Move or clear the active-pair box for ``editor``.

        Called on ``cursorPositionChanged`` and ``activeFocusChanged``. An
        unfocused editor clears its box, so two panes cannot both claim the
        active pair; the highlighter is found through the document it painted,
        the same key `attachCodeHighlighting` registered.
        """
        document = editor.property("textDocument")
        if document is None:
            return
        highlighter = self._code_highlighters.get(document.textDocument())
        if highlighter is None:
            return
        if not editor.property("activeFocus"):
            highlighter.set_cursor(None)
            return
        highlighter.set_cursor(int(editor.property("cursorPosition")))

    @Slot(QObject, int, int, str, result=bool)
    def editCode(self, editor: QObject, start: int, end: int, action: str) -> bool:
        """Apply the one editor edit ``action`` asks for at ``[start, end)``.

        The mechanics live in ``python/editing.py`` (pure Python, testable);
        this slot is only the QML door. ``editor`` is the ``TextArea`` itself,
        because the replacement is made on its ``QTextDocument`` inside one
        ``beginEditBlock``: that is what makes a wrapped selection or a
        multi-line indent **one** undo step, where QML's ``remove`` + ``insert``
        would be two. The control's own cursor is then moved with its invokable
        ``select(start, end)``.

        Returns ``False`` when the edit does not apply, and the caller must not
        consume the key — a plain character, a lone closing bracket, Backspace
        on an ordinary character.
        """
        document = editor.property("textDocument")
        text_document = None if document is None else document.textDocument()
        if text_document is None:
            return False
        edit = apply_edit(text_document.toPlainText(), start, end, action)
        if edit is None:
            return False
        if edit.replace_start != edit.replace_end or edit.text:
            cursor = QTextCursor(text_document)
            cursor.beginEditBlock()
            try:
                cursor.setPosition(edit.replace_start)
                cursor.setPosition(
                    edit.replace_end, QTextCursor.MoveMode.KeepAnchor
                )
                cursor.insertText(edit.text)
            finally:
                cursor.endEditBlock()
        # A pure caret move (stepping over a closer) must not push an empty
        # undo block; only the selection changes.
        QMetaObject.invokeMethod(
            editor,
            "select",
            Qt.ConnectionType.DirectConnection,
            Q_ARG(int, edit.selection_start),
            Q_ARG(int, edit.selection_end),
        )
        return True

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
        The result is memoized (see `_markup`): a table cell is re-evaluated on
        every resize frame while the details panel animates.
        """
        return self._markup(text, dark)

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
        plain = self._code_metrics().elidedText(
            text, Qt.TextElideMode.ElideRight, width
        )
        # The elision mark stays *outside* the spans, so it inherits the label's
        # own colour instead of the last token's — a truncated number would
        # otherwise end in a pink/red `…` whatever it truncates. `_markup` is the
        # same memo the unelided labels use, so a frame that elides to the same
        # text costs a dictionary lookup.
        if plain.endswith("\u2026"):
            return self._markup(plain[:-1], dark) + "\u2026"
        return self._markup(plain, dark)

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
