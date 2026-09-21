# Symplify — Developer Guide for Agents

> **Maintenance rule (read this first):** this file is the living handbook for
> anyone (human or agent) changing Symplify. **After any major change** — new
> source modules, renamed/moved components, architecture or data-flow changes,
> build/versioning process changes — **update the relevant section here** in the
> same commit. Stale docs are worse than none.

## What Symplify is

A desktop **symbolic calculator** (SymPy backend) with a **PySide6/QML UI** styled
by **RinUI**, following **MVVM**. UI is QML-only; business logic lives in pure
Python (`python/model/`, zero Qt). Distribution is a **Nuitka** standalone folder
built by CI on Windows.

## Source layout

```
main.py                         # Entry / composition root. Builds MainViewModel,
                                # registers flat QML context properties, then
                                # RinUIWindow loads qml/MainWindow.qml.
                                # ROOT = exe dir when frozen (Nuitka), else __file__ dir.
python/
  model/                        # PURE PYTHON, must never import Qt. The Model owns what an
                                # input MEANS (syntax, name resolution, failure kinds).
    calculator.py               #   Calculator.evaluate(expr, scope) / .assign(Assignment, scope)
                                #   -> Success | Failure; Assignment; ErrorKind; render_latex
    variable.py                 #   VariableManager (VariableEntry snapshots), validate_name,
                                #   is_sympy_name + sympy name table, classify_type
    lexer.py                    #   tokenize(text, scope) -> [(start, length, kind)]: what each run
                                #   of characters IS — never whether it is valid. Python's own
                                #   identifier/decimal rules, so it agrees with the parser.
  brackets.py                   # Rainbow bracket pairing + nesting layers (zero Qt). Ported from
                                # the v1 QWidget app's RainbowBracketsHighlighter.
  code_style.py                 # spans(text, scope): the ONE colour-span list, merging lexer.py
                                # with brackets.py; theme(family, dark) -> (styles, brackets);
                                # to_rich_text() for the read-only Text items.
  code_themes.py                # The colour families (a dark + a light member each), extracted from
                                # the themes VSCode ships; FAMILIES / DEFAULT_FAMILY / THEMES. Zero Qt.
  settings.py                   # Settings store: config dir resolution (portable data/ or the
                                # OS convention), atomic YAML read/write, validation. Zero Qt.
  rinui_bootstrap.py            # Takes RinUI's own config directory over and injects our
                                # settings; `prepare(ROOT)` is the ONLY way to import RinUI.
  window_drag.py                # Replaces RinUI's WinEventManager with one whose title-bar drag
                                # is a real caption press, and flags the drag so RinUI's own
                                # onPositionChanged move is skipped. Windows only.
  log_capture.py                # Takes over qInstallMessageHandler + sys.excepthook and feeds
                                # them to the log viewmodel, so Qt's warnings and uncaught
                                # exceptions reach the Log page instead of a console a windowed
                                # build does not have.
  viewmodel/                    # Qt bridge (QObject + models). The ONLY layer that imports Qt
                                # (besides main.py). State that must survive page switches lives here.
    input_mode.py               #   InputMode (CODE=0 / ASSIGN=1) — UI state, not model state
    main_viewmodel.py           #   Root VM; aggregates children; signals sendToCode/sendToAssign
    calculator_viewmodel.py     #   Result state, LaTeX data-URL, input persistence, clear_result
    variables_viewmodel.py      #   VariablesModel (3-col: name/expr/type) + CRUD + Qt edit protocol
    history_viewmodel.py        #   HistoryModel (QAbstractListModel, newest first, lazy LaTeX)
    search.py                   #   SearchFilterModel + Variables/HistoryFilterModel: the pages'
                                #   search boxes (proxy over the models above)
    settings_viewmodel.py       #   Settings: appearance/typography/window, config path, the only writer
    log_viewmodel.py            #   LogViewModel (formattedLogs)
    highlighter.py              #   CodeHighlighter (QSyntaxHighlighter) for TextArea.textDocument;
                                #   paints code_style spans, knows nothing about the rules
  accent.py                     # WinUI-style accent shading: RGB blends, ported from the
                                # I-Synergy ThemeColorCalculator (MIT), zero Qt
  latex_render.py               # latex_to_svg(latex, size=, color=, font=) + svg_size — theme-aware ziamath
  fonts.py                      # Font discovery: preference-list resolution, the
                                # MATH-capable fonts, .ttc extraction (zero Qt)
  keyboard_config.py            # YAML keyboard layout -> tabs; each key is
                                # {label, insert} (what it shows vs what it types)
  version.py                    # Runtime version copy (kept in sync with pyproject)
tests/
  test_model.py                 # Behaviour contract of the model + viewmodels
  test_settings.py              # Settings store, config paths, RinUI bootstrap
  __main__.py                   # `uv run python -m tests` runs every module
qml/
  MainWindow.qml                # FluentWindow + navigationItems (middle items + Log/Settings
                                # pinned bottom; do NOT give items position:Top — RinUI caps that
                                # section at 20% height and it scrolls/splits badly on short windows)
  pages/                        # Calculator / Variables / History / Log / Settings
  components/                   # Reusable pieces (+ qmldir):
                                #   CodeSurface (a code input's box, in the code theme's colours),
                                #   ExpanderRow / ExpanderPanel (RinUI expanders that keep
                                #     their content's text cursors),
                                #   PageScaffold (the frame every page shares: title, actions and
                                #     the floating bar they ride into) together with the two pieces
                                #     it assembles — PageHeader (the bar that fades in as the
                                #     inline title scrolls away) and PageHeaderRow (that title,
                                #     plus the room the actions need),
                                #   HScrollView, LatexImage, MathStrip (the formula area: HScrollView
                                #     + LatexImage + the room its overlay bar needs — the one place
                                #     that geometry lives), RadioSettingRow (a SettingItem whose
                                #     radio leads its own label), KeyboardPanel, SearchBar,
                                #   SegmentedItem/SelectorBarItem (focus-indicator shadows)
docs/
  architecture.md               # Model-first walkthrough: the two requests, the data flow
                                # (sources in, sinks out), the write path and the error kinds;
                                # architecture.svg = layer map
scripts/
  build_windows.py              # Nuitka standalone build
  release.py                    # SemVer bump (pyproject + python/version.py), optional tag
  extract_themes.py             # Regenerates code_themes.THEMES from VS Code's bundled themes (the
                                # five it ships — Atom One's data is baked in from its own files)
  cheat-sheet.md                # Human quick reference
scratch/                        # Preserved experiments — NOT part of the app and not
                                # maintained with it: test_plot.py is the SymPy->GLSL GPU
                                # plotter prototype, the future plotting track's seed
.github/workflows/build-windows.yml  # Builds on windows-latest for tags v* / manual runs
```

## Core rules & invariants

1. **`python/model/` never imports Qt**, and it is the **only** place that decides what an input
   *means* (syntax, name resolution, failure kinds). Two requests exist — `evaluate` for a read and
   `assign(Assignment, ...)` for a write — both returning `Success | Failure`. Never assemble an
   expression string in a ViewModel (that is how `x += 1` used to become the self-referential
   `x = x + 1`), and never re-implement name rules outside `validate_name` / `is_sympy_name`.
   The expression language is **SymPy's, not Python's** — probed, not assumed. `lambda t: t + 1` and
   list/dict comprehensions *do* parse (they only need their names in the scope, so `range(3)` is an
   `UNKNOWN_NAME`), but a conditional expression (`a if c else b`) and `and` / `or` / `not` are a hard
   `SYNTAX` failure, and Python builtins (`sum`, `len`, `min`, …) are unknown functions by design.
   Attribute access is **unrestricted**: `x.__class__` evaluates. Acceptable while the input is the
   user's own typing, but it is the reason this must never become a way to run *pasted* expressions
   — that change needs an AST attribute allow-list first, which is why the lexical layer here is a
   tokenizer and pointedly **not** a parser.
2. **RinUI's NavigationView destroys & recreates pages on every navigation.**
   Anything that must survive switching pages lives in a ViewModel, not QML page state.
   The Calculator page pattern: VM is the single source of truth; the Segmented control
   initializes from the VM in `Component.onCompleted` and only writes back from user
   clicks (`onClicked`) — never from `onCurrentIndexChanged` during page init (that resets
   the mode). This has regressed twice; keep the pattern.
3. **Context properties** (registered in `main.py`): `vm`, `appVersion`, `rinuiVersion`, `qtVersion`,
   `calcVM`, `varsVM`, `variablesModel`, `variablesFilter`, `historyVM`, `historyFilter`, `logVM`,
   `settingsVM`, `keyboardTabs`.
4. **Keyboard panel keys & its SelectorBar tabs use `focusPolicy: Qt.NoFocus`** so typing stays
   in the focused input. Everywhere else leave focus policy at defaults (focus ring + Ctrl+Tab).
5. **LaTeX is theme-aware**: render with `latex_to_svg(..., color=...)`; when the RinUI theme
   changes, QML (Calculator/History pages) calls `calcVM.set_latex_color` / `historyVM.set_latex_color`.
6. **Input persistence**: `calcVM.inputText / assignName / assignOperator / assignValue` persist
   across page switches.
7. **The Variables and History pages bind to search-filtered proxies** (`variablesFilter`,
   `historyFilter`) — `QSortFilterProxyModel`s over the shared models, so a query never disturbs the
   data the calculator writes into. Two consequences: every row index a page builds must come from
   the **proxy** (the table's selection model, `beginEdit`, the cell delegate — a source index there
   silently edits the wrong row), and a count that gates an *action* rather than "nothing to show"
   (e.g. Clear history) must read the **source** model. The match modes' order is a contract: the
   combo boxes pass their index straight through, so the enums in `search.py` and the `modeLabels`
   lists in the pages must stay in the same order (the tests assert it).
8. **Settings live in our own file, and only `settingsVM` writes them.** `python/settings.py` owns
   the location (portable `<root>/data/config.yaml` if that folder exists, else the OS config
   directory) and the YAML; `python/rinui_bootstrap.py` takes RinUI's own persistence over and
   **disables it** (injecting our values into `RinConfig`, then `RinConfig.save_config = noop`).
   Never re-enable RinUI's persistence, never write a settings file anywhere else, and **never
   `import RinUI` before `prepare()` has run** — that is what keeps `./RinUI/` from appearing in the
   project or install directory.

## Known RinUI / Qt traps (learned the hard way)

- Import **unversioned** `QtQuick` (`import QtQuick`) where you need current API — `import QtQuick 2.15`
  version-gates newer members (e.g. `currentRow`, `itemAtCell` revisions).
- RinUI's `TableView` sets `acceptedButtons: Qt.NoButton`, which kills its built-in
  edit triggers; the Variables page overrides it back to `Qt.LeftButton` and wires real editing
  (`flags()` `ItemIsEditable` + `model.setData`). Its `itemAtCell(a, b)` is `(column, row)`.
- RinUI's `Indicator` (selected-item accent bar) lives in the `components/` dir, but the URI
  `RinUI.AdvancedComponents` **is not importable** (module URIs resolve by directory name here, so
  app code needs `import RinUI.components`; the root `RinUI` module does not export `Indicator`).
  Its geometry is hardcoded for ~38px rows (`currentItemHeight - 23`, centered). The History page
  therefore inlines its own bar for tall/variable cards (`height: card.height - 40`, 20px inset)
  and uses `FocusIndicator` (root module) for the keyboard-focus ring. Reusing `Indicator` is
  possible but re-derives the bar from RinUI's constant (a `height - 23` bar ≈ 11.5px inset), i.e.
  it gives up the tuned 20px inset.
- `Item.visualFocus` / `Item.focusReason` **do not exist on plain `Item`** in Qt 6 (they live on
  `Control`). `FocusIndicator.control` MUST therefore be a Control (`ItemDelegate`, `Button`, …),
  not a plain `Item` — otherwise its `visible` binding throws `ReferenceError` and falls back to
  the default `visible: true`, so the focus ring shows **always**. The History page's card is an
  `ItemDelegate` (`import QtQuick.Controls.Basic 2.15 as QQC2`), with `highlighted:
  ListView.isCurrentItem`, `onActiveFocusChanged` → `historyList.currentIndex = index` (keyboard
  focus selects the card), and `FocusIndicator { control: card }`. Its list is `Rin.ListView`
  with `focusPolicy: Qt.NoFocus` so Ctrl+Tab lands on the cards (`activeFocusOnTab`), not the view.
- A History card renders as an **error card** when the model's `error` role is non-empty, and the
  only thing that changes is the result line: the failure text replaces the `= result` line, in
  `systemCriticalColor` and *wrapped* rather than elided (eliding hides the very reason the card
  exists). The input line, the background and the timestamp stay normal, there is no LaTeX strip
  (a failed request has no value), and the copy menu items are disabled. The role must be declared
  as `required property string error` on the delegate — without that line the role lands nowhere,
  `card.error` is `undefined`, and `card.error !== ""` marks **every** card as an error (the only
  clue is `Unable to assign [undefined] to QString` in the console).
- **A `ListView` has no `moveCurrentIndexUp/Down()`** — those methods belong to `GridView`; calling
  them on a ListView throws `TypeError: Property 'moveCurrentIndexDown' ... is not a function`. A
  ListView moves with `incrementCurrentIndex()` / `decrementCurrentIndex()`, which **clamp** at the
  ends (they do not wrap) and do **not** scroll, so the History page follows each move with
  `positionViewAtIndex(..., ListView.Contain)`. Selection and keyboard focus are deliberately one
  thing: `onActiveFocusChanged` makes the focused card current (Tab/click) and `onHighlightedChanged`
  → `forceActiveFocus()` makes the current card focused (arrows), so exactly one card carries both
  the accent bar and the focus ring.
- RinUI caps Top/Bottom nav sections at 20% height → keep main items unpositioned (middle) and at
  most pin a few to `Position.Bottom`.
- RinUI's `ToolTip`, `Menu`, `Dialog` are QQC2 subclasses used as **child elements** (not attached
  property syntax). Adding children of a RinUI control may fight its internal state overrides
  (e.g. disabled-state opacity) — prefer real child layout instead of `enabled` toggles.
- Merely *instantiating* `RinUI.Dialog` logs two `TypeError: Cannot read property
  'width'/'height' of null` warnings from RinUI's own `Dialog.qml` (lines 21/23) while it binds
  before being shown. Harmless and pre-existing — don't chase it; it is not a page bug.
  `Slider` does the same on construction. The settings page no longer instantiates a colour picker
  (`DropDownColorPicker` wraps `ColorPicker`, and drawing the colour inside a button that gets
  disabled in other modes was itself the problem — see the accent notes below), so that pair of
  warnings is gone with it.
- **RinUI creates its own config directory at import time**: `RinUI/core/config.py` computes
  `BASE_DIR = Path.cwd()` and writes `<cwd>/RinUI/config/rin_ui.json` when it is missing, with no
  supported way to redirect or disable it (verified against 0.4.4.1). `python/rinui_bootstrap.py`
  takes that location over — read its module docstring before touching it — and the consequences are
  an invariant: it is why `import RinUI` must never happen at module level in app code, and why
  `main.py` gets `RinUIWindow` from `prepare()` instead of from `RinUI`.
- **The settings rows size their input on purpose, not by content.** A `SettingItem` hands its
  action slot an implicit width, and the row then splits what is left between the label and the
  control *according to their content widths* — so a control whose size is not pinned resizes with
  its own text (the LaTeX family combo used to be 46% of its row while the two font-family fields
  were 61%, and none of the three lined up). The three Typography family rows therefore pin theirs
  with `Layout.preferredWidth` **and** `Layout.minimumWidth` set to `2 / 3` of the row (both: the
  preferred alone still gets shrunk, because the label's demand is content-sized too), which lands
  each at 67% with the label taking the rest. Short-choice rows (theme, backdrop, accent, language)
  keep a fixed `150` instead — the two shapes are deliberate, so match the kind of control when
  adding a row.
- **SettingCard / SettingExpander API quirks** (the published docs describe a newer version than the
  installed one): the icon is set with `icon.name:` — assigning `icon:` fails with "read-only
  property"; a `SettingCard`'s bare children land in its **right-hand** slot, while a
  `SettingExpander`'s bare children are its **collapsible content** and should be `SettingItem`s
  (`content:`/`action:` on it go to the header's right slot instead); `SettingItem` has **no**
  `content` property. RinUI *does* ship a themed `RadioButton`
  (`components/BasicInput/RadioButton.qml` — QQC2's, restyled), but like QQC2's it only unchecks its
  **siblings**: buttons in different parents are independent. A short list of choices is therefore
  `qml/components/RadioSettingRow.qml` — a `SettingItem` whose radio leads its own label, with the
  exclusivity driven by the caller's setting. Three things in it are load-bearing and easy to undo by
  accident:
  * The base's `title`/`description` are **pinned empty with a `Binding`** (not an expression, and with
    `restoreMode: Binding.RestoreNone`), so an instance cannot re-open the item's left label column:
    with that column visible the content moves to the *right-hand* slot and the radio trails the text
    — the one thing this row exists to avoid.
  * The content column carries `Layout.leftMargin: -24`. `SettingItem`'s row has `spacing: 16`, and
    with the label column collapsed RinUI's zero-width filler `Item` still counts as a neighbour
    beside our content, so the item's own inset (58) plus that spacing (16) lands the circle at 74 —
    deeper than the expander header's title. Cancelling 24 of it puts the circle at 75 against the
    header title's 77 (measured, page coordinates): aligned, and the residual 2px is RinUI's own
    label-inset (58) versus header-title (52) mismatch.
  * The click calls `selected()` **and** restores the `checked` binding
    (`checked = Qt.binding(() => root.checked)`), because Qt writes `checked` itself on the way
    through; the caller just writes its setting in `onSelected`.
  The rows go **directly** into the expander body, not behind another layout: `SettingItem` reads
  `parent.roundContentEdgeItems` for its corner rounding, so an extra `ColumnLayout` in between logs
  `Unable to assign [undefined] to bool` (SettingItem.qml:15) once per row. A `Repeater` dropped there
  is a layout child like any other and would spend `spacing` on itself before the first row, so it
  carries `visible: false`; its delegates are separate children and stay visible.
  `QtQuick.Controls` and `RinUI` both export `RadioButton`, so a page that uses RinUI's own controls
  unqualified must watch for the clash — `SettingsPage` imports `RinUI as Rin` for its `Rin.ScrollBar`
  and `RadioSettingRow` imports only `RinUI`, which keeps its `RadioButton` unambiguous; qmllint
  reports the page's other unqualified RinUI types as unresolved, an artifact of the paired imports
  (`HistoryPage` carries the same pair) rather than a runtime problem.
- **The History page deliberately does not use a `ListView`.** It is a `Flickable` + `Column` +
  `Repeater`, with the title row as an ordinary child of the content — the same shape as the Log and
  Settings pages — and that is a decision, not an accident. The list's `header` slot cost three
  separate traps: it is a `Component`, so an `id` declared in it is **invisible outside it** and the
  row has to be fetched back through `headerItem` (the tell is
  `ReferenceError: <id> is not defined`); the view does not size it, so a `RowLayout` there reports a
  height while laying every child out at width 0 until the header sets `width:` itself; and this view
  positions it *above the viewport by its own height* at rest — measured, `headerItem.y` was -64 with
  `contentY` at 0, whatever `headerPositioning` said — which leaves the page looking scrolled on
  load, title gone and the first card at the very top. What that bought was keeping delegates unbuilt
  until they scroll into view, and the lazy LaTeX behind it measures at **0.5-1.5 ms per entry**
  (cached), so the machinery is not worth it. The page now owns what the view used to:
  `currentIndex`, `keyboardNavigation`, and a `reveal(index)` standing in for
  `positionViewAtIndex`. The `headerItem`/`ListView.header` traps above remain true of any *other*
  list that wants a scrolling header — they are why this one does not.
- **A binding that names the property it defines loops.** QML resolves a bare identifier on the
  right-hand side against the object's *own* properties before the enclosing ids, so
  `PageHeaderRow { header: header }` — where the page header had `id: header` — was a self-reference:
  `Binding loop detected for property "header"`, with `PageHeader.inlineRow`'s binding looping
  alongside it. Name the ids for the role (`pageHeader`, `headerRow`) — and better, do not pass the
  object at all. The row takes `reservedWidth: frame.actionsWidth`, a *number*: the row lives inside
  the scrolling body and the actions outside it, so a reference is a loop across that boundary while
  a number keeps the dependency one-way.
- **`mapToItem` in a binding is a snapshot of where things are *now*, scroll included.** `PageHeader`
  finds its inline row with `inlineRow.mapToItem(flickable, 0, 0).y`, and `travellingY` then subtracts
  the flickable's scroll — so the scroll has to come back off at the mapping. Otherwise it is counted
  twice, the actions move at twice the scroll rate, and they end up tens of pixels below the row they
  belong beside. Worse, the error **persists**: a `mapToItem` call creates no dependency on the
  positions it reads, so the property keeps whatever it saw when the binding last ran and the actions
  stay displaced after the gesture ends. Mapping into the flickable and adding `contentY` back gives
  the row's position in *content* coordinates (what the rest of the maths assumes), and that is
  stable, because scrolling does not change it. Clamping the scroll (`Math.max(0, contentY)`) hides
  the symptom without fixing the frame of reference — it lived in this file for a round, and the
  drift came straight back the moment it was removed.
- **Overscroll and its bounce are the native ones; nothing here needs to manage them.** An earlier
  round set `boundsBehavior: Flickable.StopAtBounds` on every page body (and clamped `contentY` in
  `PageHeader`) to stop a list being dragged past its end. All of it is gone. The stretched state
  that prompted it was never the overscroll — it was the coordinate bug above, and what looked like
  "the content stays where I dragged it" was the actions parked at a double-counted offset.
  `Rin.ListView`'s own `updateAnimation` (which pulls `contentY` to -12 and back on every model
  change) is left alone too: it is part of the list's feel. Verified by measuring screenshots:
  idle, mid-drag and settled all put the toolbar 2px from the title, at the same absolute y.
- **Do not hand-roll a page scroll bar; attach RinUI's.** The History page once showed two bars,
  because the list's own attached bar and a hand-written page-level one were both drawn — and the
  hand-written one, built on `T.ScrollBar`, was broken in the two ways an attached bar is immune to:
  Qt sizes and places an *attached* bar's content item from `size`/`position` (a free-standing one
  must do it itself, and the first attempt drew a **full-height line that never moved** — a permanent
  stripe down the window edge of every page), and an attached bar's `active` is driven for it
  (deriving it here deadlocked: hiding on `!active` while `active` includes `hovered` means an item
  that is never visible and so can never be hovered). Note also that **nothing written through the
  `verticalScrollBar` alias removes an attached bar**: the assignment raises no warning and does
  nothing, because the bar binds `policy` itself — only declaring `ScrollBar.vertical: null` on the
  view drops it. The pages therefore keep what the view already had: `Rin.ListView` attaches RinUI's
  bar itself, and the `Flickable` pages add `Rin.ScrollBar.vertical: Rin.ScrollBar {}`. One bar, at
  the right edge of the view that scrolls — which is why the History list is deliberately
  **full-bleed**: that puts its bar on the window edge, where the Microsoft Store keeps it, and the
  *cards* carry the inset instead: the content sits at the usual 24px and the cards add
  `page.cardInset` (4px) on each side. Note the painted bar is tiny — RinUI's thumb is
  `scrollBarWidth` (6px) when hovered, 2px idle, inside a 12px interaction zone — so the cards'
  32px stand-off from the edge is plenty; nothing needs to give way for it. The real overlay fight
  is *inside* a strip that scrolls horizontally: RinUI's bar is an overlay along the bottom edge,
  ~16px tall in all (6px thumb plus the arrow `ToolButton`s, which overhang the 12px control), so a
  formula with only 8px under it has the arrows sitting on its feet. That clearance belongs to
  `MathStrip` (`barRoom`), not to each page — two hand-written copies of that arithmetic is what
  clipped the Calculator's formula.
- **A page loaded outside `MainWindow.qml` renders RinUI's control text and icons blank.** Driving
  a page from a test harness (`Loader { source: "pages/SettingsPage.qml" }`) skips `FluentWindow`,
  which is where RinUI's icon fonts and typography are set up: every `Button`, `RadioButton` and
  `SettingItem` label comes out invisible, which reads as a page bug and is not one. Load the page
  inside a `FluentWindow` root instead (`FluentWindow { Loader { anchors.fill: parent; source: … } }`)
  and the text renders — the code-font labels and rendered LaTeX are unaffected either way, so a
  geometry check can pass while every control looks empty.
- **A harness that drives the app must isolate the settings store, or it writes the developer's own
  config.** `SettingsStore` is portable only when **`<root>/data` exists**, so `prepare(tmp)` with
  `tmp` being a bare temp dir falls back to the OS config directory and the run reads *and writes*
  the real `%APPDATA%/Symplify/config.yaml` — a probe that clicks a radio silently changed
  `appearance.code_theme` once. Pass a temp directory that *contains* `data/`
  (`root = mkdtemp(); (root / "data").mkdir()`), and print `runtime.settings.path` at the start of
  the run so the isolation is visible rather than assumed.
- **`findChildren` from Python does not see `Repeater`-created delegates.** Measured on the History
  cards and the settings rows: QML's `repeater.itemAt(0)` returns the created `ItemDelegate`, while
  `window.findChildren(QObject)` from PySide6 does not reach it (nor the `Image` inside its
  `MathStrip`). A harness that needs their geometry has to ask from QML — walk `children` and match
  on `objectName`, as `qml/components/…` hooks like `sendBtn` and `codeThemeRows` exist for.
- **Never resize a RinUI window while it is being created and then maximize it.** The window fills
  the screen but its content stays drawn in the pre-resize rectangle, surrounded by a white border,
  and later resizes never repair it — while Qt reports the correct window state *and* content size,
  so the desync is purely in the presentation layer (Mica / DWM). Observed fixes and their reasons:
  the remembered **size** is set declaratively in `MainWindow.qml`
  (`width: settingsVM.startupWidth`), so the window is created at the right size and never resized;
  the **position** is applied after creation (a move is safe) — and even when the window starts
  maximized, because that x/y becomes the rect a restore-from-maximized returns to (left unset it is
  the screen's corner, where such a window then lands); and the **maximized** state uses
  `showMaximized()` once the window is visible, because maximizing before it is shown has the same
  stale effect (as does `setWindowState(WindowMaximized)` afterwards). Verified against RinUI 0.4.4.1
  on Windows 11 — when touching window geometry, check it visually, Qt values can look perfect.
- **RinUI's title bar moves the window twice: once natively, once by hand.** `TitleBar.qml`'s
  `onPressed` starts a *native* system move, but its `onPositionChanged` also runs
  `window.setX(window.x + delta.x)`. The guard meant to skip that on Windows tests
  `Qt.platform.os !== "windows"`, so it returns everywhere *except* Windows — and its other two
  disjuncts (`window.isMaximized`, `window.isFullScreen`) are never defined by RinUI at all, so the
  guard only ever saw `visibility`. The manual move stays invisible until the window is dragged out
  of fullscreen: the un-maximize shifts the title bar's local coordinates by half the width
  difference, so the first event after it computes a delta of roughly `-(width/2)` and teleports the
  window — measured from `(395, 277)` to `(0, 300)`, i.e. the drag's offset from the screen's
  top-left corner. Ordinary apps do not do this (Paint lands on `(256, 277)` and stays there).
  Fixed from our side: `python/window_drag.py` replaces the manager class (RinUI builds it with
  `from .window import WinEventManager` *inside* the constructor, so replacing the name is enough)
  to send `WM_NCLBUTTONDOWN`/`HTCAPTION` — a real caption press, which needs no cursor coordinates
  to get wrong — and to raise `dragInProgress` on the window for the whole gesture.
  `MainWindow.qml` folds that into `isMaximized`, which is what the guard reads, so the manual move
  is skipped. The zero-timer that clears the flag is deliberate: the mouse events the system move
  leaves queued are handled *after* `SendMessage` returns. Verified against RinUI 0.4.4.1 —
  windowed drag, title-bar double-click, Aero Snap and the drag-out of a maximized window all
  behave like a native app.
- **A bare `QQuickView` can hang on components that touch the `Theme` singleton** — `Expander`
  (hence `SettingExpander`) spins forever during construction when the engine has no `ThemeManager`
  context property, instead of merely warning like the other singleton uses. The app is fine
  (`RinUIWindow` registers it, and can host the settings page); a throwaway probe must either
  register a `ThemeManager` or load the page through `RinUIWindow`.

- **A QQC2 `ScrollView` creates its scroll bars inside the style's own file, so the importing
  page cannot name them — but it can replace them.** Every style's `ScrollView.qml` does
  `ScrollBar.vertical: ScrollBar { … }` in its own context, where `ScrollBar` resolves to *that
  style*. A page that imports `QtQuick.Controls` therefore gets the style's groove-and-handle bar
  (a wide grey trough laid over the text) even though every other surface in the app uses RinUI's
  bars. The fix is to re-declare the bars on the instance —
  `ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }` — which is exactly what RinUI's
  own (unregistered) `components/ScrollView.qml` does. Two corollaries: the same override does
  nothing for a plain `Flickable` (it has no style-made bars to replace), and a page that imports
  `QtQuick.Controls` under a namespace must qualify the container too (`QQC2.ScrollView`) — a bare
  `ScrollView` there is a hard "is not a type" at load, which RinUI surfaces as its error page.
- **The Log and the Calculator's code input are RinUI `ScrollableTextArea`s.** Two things come with
  that component. (1) It logs `ReferenceError: defaultHeight is not defined` on every instance —
  line 20 binds `implicitHeight` to a property that does not exist. That is RinUI's own bug, its
  gallery example triggers it too, and it is harmless noise: don't chase it. (2) **It does not
  scroll.** An instrumented run with 80 log lines left the view on the *oldest* entry with the rest
  clipped by the card and no bar, identical with and without pinning `implicitHeight` on the
  instance. The tail-follow itself is one line —
  `onTextChanged: textArea.cursorPosition = textArea.length` — but whether the pane scrolls at all
  for overflowing content is still unverified.
  The `Flickable` + `TextEdit` version that preceded it **did** scroll, and is worth remembering if
  the wrapper ever has to go: drive `contentY` imperatively from `onContentHeightChanged`, because a
  binding on `contentY` breaks the moment a Flickable writes that property itself. Its attached
  `ScrollBar` never became visible in the captures either.

- **Only `TextArea` / `TextEdit` expose `textDocument`, so only they can take a code highlighter.**
  QQC2's `TextField` does not — probed, not assumed: `typeof tf.textDocument === "undefined"`, against
  `"object"` for `TextArea`. That is why the Assign *value* field is a `TextArea` while the *name*
  field stays a `TextField` — there is no expression to colour in a name. The `TextArea` wears the
  field's manners explicitly: `textFormat: TextEdit.PlainText` (expressions hold `<` and `&`, which
  the rich-text auto-detection would swallow) and a `Keys.onPressed` that runs the calculation on
  Enter instead of inserting a newline — plus Backspace in an empty value, which focuses the name.
  It **wraps** (`wrapMode: TextEdit.Wrap`), so a long expression grows the row instead of scrolling
  sideways; the row's height is capped (`Math.min(240, Math.max(110, assignRow.implicitHeight + 8))`)
  so the input area adapts while staying bounded.
- **Two probe results worth keeping even though the value field no longer uses that design.** A
  `Flickable` does **not** keep the caret in view (with the caret at the end of a line wider than the
  viewport, `contentX` stayed `0`), so a `NoWrap` `TextArea` inside an `HScrollView` has to nudge
  `contentX` itself from `onCursorRectangleChanged`; and the box such a field sits in has to be
  *outside* the scroller, or the border stretches with the content and scrolls away with it, making
  the field look broken as soon as the expression is wider than its box. That shell-plus-`HScrollView`
  version was built and then reverted in favour of the wrapping field above; the backup is
  `build/CalculatorPage.qml.shell-backup` (gitignored) if it is ever wanted back.
- **`TextField` exposes no assignable `contentItem`** — unlike `Button` and `ItemDelegate`, where that
  override is routine (and routine in this repo, on `DropDownColorPicker`). QML refuses it outright:
  *"Cannot assign to non-existent property contentItem"*.

- **A `ScrollView` sizes its content to the viewport, and a rich text `TextArea` inside one never
  settles.** Changing the text area's width (a scroll bar appearing, a padding change) re-wraps the
  text, which changes its height, which asks for the bar again. Measured on the Log page: the
  flickable's `contentHeight` crawled 279 → 288 → 311 → 342 → 377 while the text itself reported
  6290 — a few hundred pixels of scrollable range against ~6000 of text, so the tail was
  unreachable, and binding `implicitHeight: contentHeight + paddings` on the text area did not
  change it. What works is the Settings page's arrangement: a `Flickable` that declares its own
  `contentHeight` from the content's real height. Reach for that whenever the content's size is
  known — it is also what makes the attached `ScrollBar` hug the window edge.
- **A QML `color` handed to Python is a `QColor`, and `str()` on it is not a colour.** `QColor.__str__`
  gives `PySide6.QtGui.QColor.fromRgbF(1.000000, …)`, so a rich-text string built from it fails with
  `QTextHtmlParser::applyAttributes: Unknown color name` and the text silently keeps the default
  colour. Convert where the value is still a colour (QML: `Qt.rgba(...).toString()`; Python:
  `QColor.name()`). And note the theme's roles are translucent (`Qt.alpha()`), so `name()` alone
  drops the alpha and the ink comes out too bright — composite over the background first.

- **A backdrop built by hand draws the sharp copy as well as the blurred one.** RinUI ships
  `AcrylicBrush` (root `RinUI` module, `components/Styles/`) for exactly this: assign `sourceItem` and
  it captures the band it covers, keeps its own capture item invisible, tints it with the theme's
  acrylic colour, and falls back to a tinted fill when the effect is unavailable. A header that
  instead kept a *visible* `ShaderEffectSource` and stacked a `MultiEffect` of it on top superimposed
  the two — a blur of sparse text is mostly transparent, so the sharp text showed through it,
  legible but with frayed edges. Use the material; and note that a hidden `ShaderEffectSource` still
  provides its texture, which is what makes the library's own arrangement work. One structural
  consequence follows for a *floating* bar: it is a sibling **above** the flickable while the scroll
  bar lives **inside** it, so nothing in the flickable can ever be drawn over the bar — which is why
  the header's scroll bar is a page-level sibling too (see the trap below) rather than the attached
  one, letting the bar's outer margin simply equal its corner radius.

- **A `ScrollBar` from `QtQuick.Controls` — or RinUI's (`components/ScrollBar.qml`), which is built
  on that type — cannot be used free-standing.** A plain instance logs two warnings:
  `Cannot specify top, bottom, and verticalCenter anchors at the same time` (the Controls type
  anchors itself) and `ScrollBar attached property must be attached to an object deriving from
  Flickable or ScrollView` (it declares that property). RinUI's own comment says it imports
  `QtQuick.Templates` for a related reason. Extending `T.ScrollBar` to get a free-standing one is
  possible — and is what a page-level bar here once did, badly enough to be worth avoiding (see the
  two-scroll-bars bullet above). Attaching RinUI's bar is what the pages do now; it also means the
  bar is not part of `PageScaffold`, which draws only what must not scroll.

## Rendering / display

- LaTeX: `Success.latex` (`Calculator.render_latex`, sympy) → VM builds a percent-encoded SVG
  **data URL** (`latex_render.latex_to_svg`, with `size=`/`color=`), `svg_size` for natural size;
  `LatexImage` (qml/components) renders crisp by scaling `sourceSize` by `devicePixelRatio`.
  The font size comes from the settings page (`fonts.latex_size`), the colour from the theme.
- **`MathStrip` is the one place a rendered formula is laid out** — the Calculator's result area,
  the History card's strip, and (when the Variables page grows one) any third caller. It is an
  `HScrollView` whose content is a single `LatexImage` at natural size, and it owns both pieces of
  arithmetic that used to be hand-written per page: the height (`natural + 2*padding + barRoom`)
  and the image's `y` (`padding` from the top). Those two numbers in two coordinate systems is
  exactly what broke: both pages carried `y: (parent.height - height - 16) / 2`, the image's parent
  was the strip on one page and an inner content `Item` on the other, and on the Calculator that
  resolved to -8 — the formula's top was clipped. It takes `naturalWidth/naturalHeight/source` and
  collapses to zero height when there is no artwork; it carries **no** empty-state text (the
  Calculator's failure and hint live on its outcome line, the History card's failure on its result
  line). `barRoom` (16) is the height of RinUI's overlay bar along the strip's bottom edge — a 6px
  thumb inside a 12px control, plus the 16px arrow `ToolButton`s that overhang it — and is
  deliberately hardcoded against a third party's internals, in this one place.
- History renders each entry's LaTeX **lazily, per row, on approach**, and the pieces of that are
  worth stating because two obvious implementations do not work. Reading the `latexUrl` role used to
  render (the model's `_svg_url` caches the SVG on the entry and emits `dataChanged` for the
  LaTeX/natural-size roles). That made *reading* the role the cost, so the read had to be deferred —
  but a role can only be read where it is *injected*, which is the delegate root, so neither
  `model.latexUrl` (there is no `model` object in a `Repeater` delegate) nor a `Loader`-wrapped
  sub-component (a `Component` inside a delegate does not inherit the model context, and every
  `required property` comes back uninitialised) can defer it. The render moved out of the read
  instead: `data()` now only looks the SVG up, and the view calls `historyVM.requestLatex(index)`
  while the card is near the viewport (`nearView`, one screen of slack) — and again when the cache
  was dropped under it by a theme change, which shows up as the role going back to empty.
- **The page loads in batches, and the `Column` makes that cheap.** Only `page.loaded` cards (12 to
  start) are `visible`; the rest are skipped by the `Column`, so they occupy no space and the content
  only ever spans what is loaded. `maybeLoadMore()` raises `loaded` by another batch when the reader
  is within 320px of the loaded bottom. It is a *single* step that re-queues itself with
  `Qt.callLater` after the new cards' layout, not a loop (a loop reads a stale `contentHeight` and
  pours everything in) and not a `contentHeightChanged` handler (Qt swallows the re-entrant emission,
  stalling the chain one batch after a resize). Beyond `onContentYChanged` it also runs on page
  completion and on flickable height changes, because a window too tall for one batch has nothing to
  scroll — without those, the rest of the history is unreachable. One trap:
  `nearView` has to test `visible` *first*, because a skipped card has no position of its own and `y`
  reads 0 — which the geometry test otherwise takes for "at the top of the viewport", and every
  unloaded card renders.
- **Set the LaTeX colour before any page is built.** The pages used to do it in their own
  `Component.onCompleted`, which runs after their delegates exist: every entry rendered once in the
  default black, then the colour arrived, dropped the whole cache, and every entry rendered again.
  `MainWindow` sets it with the log colours now (`applyLatexColors`), and the log — mirrored to the
  terminal — is what made the doubling obvious.
- Long results/text use `elide: ElideRight` (mono lines in history align the result `=` under the
  assignment operator via `" ".repeat(name.length + 1)`).

## Code colouring

One lexer, one span list, two renderers. Anything that colours code contributes spans to
`code_style.spans(text, scope)`, and nothing paints on its own.

- **The lexical truth is `model/lexer.py`** — a tokenizer, not a parser and not a judge. It says
  what each run of characters *is*; whether the expression is valid stays with `Calculator.evaluate`
  (`Success` / `Failure`). That split is the point: `implicit_multiplication` turns `foo(1)` into
  `f*o**2`, so a highlighter deciding for itself would call it a function call while
  `unknown_calls` reports it as an unknown one.
- Character classes come from Python itself (`str.isidentifier` to continue a name, **`isdecimal`**
  for digits — never `isalnum`/`isdigit`, which accept superscripts). The parser tokenizes with
  Python's tokenizer, so this agrees with it for free.
- **No AST — and don't write one.** `parse_expr` already yields a sympy tree; what it lacks is source
  positions, and positions are what a tokenizer gives. Hover, completion and error ranges work off
  tokens plus the answers the model already produces; none of them needs a second tree.
- **Brackets** (`brackets.py`, ported from the v1 app) are paired over the *whole document*, not per
  block, so a bracket closed on the next line keeps its partner's colour. A stray bracket gets no
  layer, so it cannot shift the colours of the pairs around it.
- **Renderers**: `viewmodel/highlighter.py` (`QSyntaxHighlighter`, attached to the editable input's
  `textArea.textDocument`) and `code_style.to_rich_text` (markup, for read-only `Text` items). A
  second painter would lose — `setFormat` is last-write-wins, so two highlighters on one document
  erase each other. A future Pygments, or any other language, becomes another *span producer*
  behind the same function, never a second painter. The read-only labels use the
  second renderer: `vm.highlighted(text, dark)` returns the markup and the pages
  bind it into a `Text` with `textFormat: Text.RichText` — the Calculator's outcome
  line (value, failure text or hint), the History card's two lines, and the
  Variables table's cells (the last two inside delegate bindings, so only the rows
  a view actually has out are rendered, and a theme change re-evaluates them).
  The formula area itself is not one of these: it is an image (`MathStrip`).
  Two things come with that, both learned the hard way: `to_rich_text` takes the
  scope as a **mapping** where `attach` takes the **provider** (the highlighter
  re-asks on every keystroke; a one-shot render cannot), and handing the provider
  to both raises `argument of type 'method' is not iterable` *inside the QML
  binding* — invisible on an expression of digits and brackets, and every label
  holding a name blank or stale. And rich text collapses runs of spaces, so the
  History card's `=`-alignment padding is `&nbsp;` — the one place the markup leaks
  into the surrounding text.
- **`Text.elide` is silently ignored for `Text.RichText`** — probed on Qt 6.11:
  plain and styled text truncate, rich text paints at its full painted width and
  bleeds over whatever sits beside it (that was the overflow on the Calculator's
  result line, the History card's two lines and the Variables cells). The
  escape hatch, `Text.StyledText`, is not one: it parses `<span style="color:…">`
  but renders `&nbsp;` and even `&lt;` **literally**, so switching would break
  the escaping and the `=`-alignment padding. The elision therefore happens on
  the plain string, in `vm.highlightedElided(text, width, dark)` — the code
  font's `QFontMetricsF.elidedText` runs *before* the span list, and the elision
  mark is just another character to the highlighter. Callers pass their label's
  own `width` (minus a measured prefix where one exists — `TextMetrics` with a
  no-break space, which advances like a plain one). Two consequences to keep:
  those labels sit in layouts, whose default minimum width is the item's
  implicit — for rich text the *full* text's width, so the row would grow past
  the panel instead of squeezing the label; every code label in a `RowLayout`
  carries `Layout.minimumWidth: 0` for that. And the label's `text` binding now
  depends on its `width` — safe from loops because the layout width no longer
  reads the implicit width.
- **The colours come from a theme *family*, not from a single theme.** `python/code_themes.py` holds
  one entry per family — Atom One, VS Code Dark+/Light+, Dark/Light Modern, Dark/Light 2026,
  Solarized, High Contrast — and **every family has a dark and a light member**, so
  `code_style.theme(family, dark)` always answers: it returns `(styles, bracket_colors)` for the
  half that matches the UI. `appearance.code_theme` names the family and the *page* passes
  `Theme.isDark()`, so the two compose — the family says which colours, the UI theme says which half
  of it. A family that could answer for only one side would leave the code bare the moment the UI
  flipped, which is the point of pairing them.
  The data is **baked into the repository** — the app reads neither a VS Code install nor the network
  at run time. `scripts/extract_themes.py` regenerates **every** family from raw files on GitHub,
  pinned to a tag or a commit: VS Code's five paired themes from `microsoft/vscode` (at `VSCODE_REF`,
  the release whose editor the colours are meant to match), Atom One Dark/Light from
  `akamud/vscode-theme-onedark` and its light counterpart. Pinning is what makes it reproducible —
  the same ref always yields the same table, and the script reproduces the committed one exactly,
  family by family — so bumping a pin is a reviewable change rather than a background drift. Two
  things come with reading upstream files rather than an installed editor: they are **JSONC**
  (`//` comments and trailing commas, which VS Code's own build strips from the copies it ships), and
  their `include` chains have to be followed by hand. Both are handled in the script; a fetch that
  cannot reach GitHub fails loudly, and the committed data is unaffected.
  `OVERRIDES` there records the one place the app does not take a theme's word for it: Atom One names
  the literal colour `white` for `invalid`, invisible on its own light background and
  indistinguishable from text on its dark one.
  Scopes map onto our kinds — `constant.numeric` for numbers, `constant.language`/`variable.language`
  for SymPy constants, `entity.name.function`/`support.function` for callables, `variable.other` for
  stored variables, `keyword.operator` for operators. A style a family omits is simply not painted,
  and the families differ in what they omit and in what they paint alike: Solarized names no
  keyword operator, so its operators keep the control's own ink, where Light+'s are its `#ee0000`;
  Atom One paints a stored variable with the theme's own foreground, so there it reads like any
  other text. A free symbol is never coloured. `DEFAULT_STYLES` is the fallback when the family is
  unknown (a config naming one this build no longer has): `theme()` returns it rather than raising.
- **The page passes `Theme.isDark()` along with the document.** RinUI resolves `Auto` against the
  OS, so the *effective* theme decides, not the setting. `attachCodeHighlighting` reads the family
  from the settings at that moment, and `highlighter.attach` parents the highlighter to the document
  — so a changed family, or a flipped UI theme, lands when the page is next built, which RinUI's
  rebuild on navigation is what causes. Verified from the rendered pixels, no restart: the same
  expression gives `#b5cea8` digits under Dark+ (dark), `#098658` and `#ee0000` under Light+ once the
  UI is switched to Light, and `#d33682` under Solarized.
- **`MainViewModel._settings` is the settings *viewmodel*, not the store.** Read settings through its
  properties (`self._settings.codeTheme`, like `latexSize` beside it). A store call on it
  (`self._settings.get("appearance.code_theme")`) raises *inside the QML slot*, where it is a line in
  the log and the feature quietly does nothing — which is how the code colouring once broke with
  every palette test still green. `test_attaching_the_colouring_paints_the_named_family` covers that
  seam: it fails with the store call and passes with the property.
- **Brackets take the family's colours when it names any, and the rainbow when it does not.**
  Solarized is the one family here that carries an `editorBracketHighlight`, and only its *dark*
  half does — every other family, and Solarized light, gets `brackets.DEFAULT_COLORS` (the v1
  rainbow). So an empty tuple from `theme()` means "this family has nothing to say about brackets",
  not "no brackets"; the renderer supplies the rainbow in that case. `color_for` is where that
  substitution happens — it owns both fallbacks (`None`/empty → the default palette or the rainbow),
  so the highlighter and `to_rich_text` cannot disagree about it. Reading the empty tuple as "a
  palette of zero colours" is what once divided by zero there, and because it blew up inside the
  highlighter's recompute — *before* `rehighlight()` — the input kept the **previous** text's
  formats: left brackets underlined as unmatched, right ones bare, and every later refresh (typing,
  pasting, a theme switch) dying the same way. `to_rich_text` was a live trap too: it is what the
  History cards use, and it asks the same function.
  `test_a_family_with_no_bracket_colours_paints_the_rainbow` and
  `test_an_empty_bracket_palette_means_no_opinion` hold that down.
- **The input's surface is the family's too.** `code_style.surface(family, dark)` answers
  `(background, ink)` — the theme's `editor.background` and `editor.foreground` — and
  `settingsVM.codeSurface(dark)` hands QML the `{background, ink}` map the page binds to.
  `qml/components/CodeSurface.qml` replaces the text area's `background:` (RinUI's chrome redrawn in
  that colour: rounded to `buttonRadius`, bordered, accent underline while focused, clipped to the
  rounding through an OpacityMask), and the page paints the control's `color` with the ink so text
  the palette leaves unpainted stays legible on it — Solarized has no `keyword.operator`, so its
  operators are exactly that case. The **placeholder** is the theme's too:
  `input.placeholderForeground` where the theme names one (Solarized's carry an
  alpha), and otherwise VSCode's own derivation of it — `transparent(foreground,
  0.5)`, `0.7` in high contrast, with VSCode's default `foreground` when the theme
  leaves that unset as well (Atom One and High Contrast do). The extractor resolves
  that alpha against the background, because these inputs have exactly one surface;
  it also keeps `#RRGGBBAA` out of QML, where eight digits would mean *AARRGGBB*.
  A family that names no background gets no placeholder either — its surface is not
  the theme's, so neither is what is written faintly on it.
  **Only the code inputs get it** — the Code box, the Assign value
  and the Assign *name* field, each by replacing its own `background:` (RinUI's `TextArea` and
  `TextField` carry the same chrome; `contentItem` is the one a `TextField` will not give up —
  `background` it will). An editor differs from its panels, so the operator dropdown, the result
  line, the history cards and the tables keep the UI theme. The name field takes the ink too: it is
  plain text — nothing highlights a name — but it sits on the same surface as the expressions beside
  it, so it reads in the same colour. The inner area's
  background has to be nulled, or RinUI's opaque `controlColor` covers the replacement. An empty
  value is "no opinion" — High Contrast Light states neither colour — and the UI theme's own colours
  stand in, the same rule the bracket palette follows.
  Verified from the rendered pixels: Solarized on a dark UI gives the box `#002b36` with `#839496`
  text and `#cdcdcd` brackets, and on a light UI `#fdf6e3` (its cream) with the rainbow brackets,
  since that half carries no `editorBracketHighlight`.
- **Cost**: the whole document is re-scanned and rehighlighted on every change, because pairing
  spans lines. Fine for an input of a few hundred characters; do **not** attach it to the Log
  (appended to constantly, grows without bound) or to anything long that changes often. Markup for a
  read-only display belongs in the entry's own data, computed once — never inside `data()`, which
  runs on every repaint.

## Log

The Log page shows one stream, arriving from two directions, and it is the app's only window into
its own health.

**Into the page.** `python/log_capture.py` takes over `qInstallMessageHandler` and `sys.excepthook`
and hands both to `LogViewModel`. Before it, Qt's warnings went to a console a packaged build does
not have (`--windows-console-mode=disable` leaves `sys.stdout` as `None`), and an uncaught exception
went nowhere the user could look. What that stream carries is not academic: RinUI emits
`ScrollableTextArea.qml:20 … ReferenceError: defaultHeight is not defined` on every instantiation,
and `Dialog.qml:21/23 … TypeError: Cannot read property 'width'/'height' of null` — all of them
visible in the page now, invisible before. The Qt handler must not re-enter itself (it ends in a
signal emission that can make Qt print again), so a module flag drops nested calls.

**Everything also goes to the terminal**, through `LogViewModel.entryAdded` — one signal, so the page
and the terminal cannot drift apart. Levels are routed: DEBUG/INFO to stdout, WARNING/ERROR to
stderr, written through `sys.__stdout__`/`sys.__stderr__` (the streams the interpreter started with)
and flushed, because a redirected stream is block-buffered and a developer watching a file wants the
line now. This is deliberate and it is what the earlier version of this file refused to do: without
it, a headless run — or any run where nobody is looking at the window — leaves every message in a
page nobody can read, and the app's own probes (a temporary `print`) simply vanish. The excepthook
therefore no longer chains to Python's own: the entry *is* the traceback, and mirroring it prints it
once.

**Entries.** Consecutive identical entries collapse into one line with an `(xN)` count (that RinUI
warning arrives once per instantiation), and the list is capped at `MAX_ENTRIES = 1000`, which also
bounds the rich text rebuild on every append.

**Colours come from QML**, not from Python: they are RinUI's status roles — `systemAttentionColor`
for INFO, `systemCautionColor` for WARNING, `systemCriticalColor` for ERROR, `textTertialyColor` for
DEBUG — and the theme lives on that side. `MainWindow.qml` pushes them with `logVM.colors = {…}`,
and it has to convert on the way: a `color` handed to Python arrives as a `QColor` whose `str()` is
`PySide6.QtGui.QColor.fromRgbF(…)`, which Qt's rich-text parser rejects with `Unknown color name`.
The values are composited over the page background (theme roles are translucent) and emitted as
opaque `#rrggbb`.

**The page** (`qml/pages/LogPage.qml`) is a borderless `Flickable` + rich `Text`, deliberately not a
`ScrollView` — see the trap below. It follows the tail unless the reader has scrolled away, and it
distinguishes "not laid out yet" from "scrolled up"; conflating the two is what left the page
opening on its oldest line. Its header is the two-part arrangement the Microsoft Store uses — the
title, the actions and the bar in `qml/components/PageHeader.qml`, the inline row in
`PageHeaderRow.qml`, and both assembled for every page by `PageScaffold.qml`; the scroll bar is not
part of this at all — it belongs to the body, which attaches RinUI's (see the trap above). The title
is content — the first thing in the column, on the
ordinary page background — and scrolls away with everything else, while the *actions* are not
content. There is exactly one copy of the actions, owned by that component, and they travel: their
`y` tracks the inline row up the page and stops, centred, at the bar's resting place, so they ride
the content and then stick under a rounded acrylic bar. (One copy is also what stops a
scrolled-away set from still being clickable, which a second, hidden instance would be.) The bar's
backdrop floats up from 10px below while fading in, and carries the page's own title as it does.

## Settings & config

- One YAML file, written **only** by `SettingsViewModel` (invariant 8). The schema, defaults and
  validation live in `python/settings.py` (`DEFAULTS`): unknown keys survive a rewrite, invalid
  values fall back or clamp, writes are atomic (temp file + `os.replace`), and a read-only location
  degrades to in-memory values with a warning the page displays. Keys:
  `appearance.theme|backdrop|code_theme|accent|accent_mode|accent_shading|accent_os_shading`,
  `fonts.code_family|code_size|keyboard_family|keyboard_size|latex_font|latex_size`,
  `window.remember|width|height|x|y|maximized`. The page groups them under the subtitles
  **Interface / Typography / Language / Settings file / About**. Layout follows RinUI's own gallery
  (`examples/pages/Settings.qml`): a section is a `ColumnLayout { spacing: 3 }` holding a
  **`Typography.BodyStrong`** subtitle and then one card per row, and the sections are separated by
  the outer column's spacing. Subtitle size is the gallery's, not a guess — `BodyStrong` renders at
  the theme's `bodyStrongSize` (14 pt, weight 600), i.e. *the same size as a card title but bolder*;
  `Typography.Subtitle` (20 pt) is one size too large and reads as a second page heading. Most rows
  are `SettingCard`s; a `SettingExpander` is used only where a row carries a second row of its own
    (the code theme, accent and About groups). The code theme's holds one cell per family — a `Flow`
  of fixed-width columns, each a `RadioButton` over a wrapped line of description — so the choices
  read as one row and wrap only when the window is narrow. `fonts.latex_size` used to be `rendering.latex_size`: `load()`
  migrates it, and a file that has both keeps the new key.
- **Location**: `<root>/data/config.yaml` when a `data` folder sits next to the app (portable mode;
  `root` is the exe directory when frozen and the repository root in dev), otherwise the OS
  convention — `%APPDATA%\Symplify\` (Windows, falls back to `%LOCALAPPDATA%`),
  `$XDG_CONFIG_HOME/symplify/` (Linux, falls back to `~/.config/symplify/`),
  `~/Library/Application Support/Symplify/` (macOS). The settings page shows the resolved path and
  mode, and clicking that row opens the folder.
- Appearance is applied through RinUI's `ThemeManager` (the QML `Theme` singleton wraps it), injected
  before the window exists so the first frame is already themed. Theme and backdrop apply fine
  through the Python slots.
- **The accent has three modes, and the mode — not the stored colour — decides what is applied**
  (`appearance.accent_mode`): `default` is RinUI's own `#605ed2` (also `DEFAULTS["appearance"]["accent"]`),
  `system` is `QPalette.Highlight` (the OS accent colour), `custom` is the picked
  `appearance.accent`. `SettingsViewModel` resolves the mode: `accent` is a **read-only** property
  returning the colour in effect, `customAccent` is the stored pick, and `accentChanged` announces
  the result. Consequences worth keeping:
  - RinUI's Python `set_theme_color` only persists the value; what re-colours the controls is
    `Utils.primaryColor`, which its QML `Theme.setThemeColor` sets as well. So **only QML applies
    the accent**, and `MainWindow.qml` is its **single owner** (`applyAccent()`): the window
    outlives the pages, and applying it has to happen at startup, on every change, *and* after every
    theme switch, which a page cannot do. Pages must not touch it.
  - **The accent's variants are RGB blends, ported from the C# `ThemeColorCalculator`**
    (I-Synergy Framework, `ThemeColorCalculatorTests.cs`). `white_blend(c, f)` mixes towards white,
    `black_blend(c, f)` towards black, and the palette is the trio **`tertiary`** (darker, −25%) /
    **primary** / **`secondary`** (lighter, +25%). The scheme mapping follows the framework's own
    semantics: **light takes `tertiary`, dark takes `secondary`**. Both blends are monotonic and
    self-clamping, which is why that framework's tests assert properties rather than values. This
    replaced an HSL-step family (`SHADE_STEPS` + WinUI's `Light1..3` formula).
  - The framework's other half, **`tinted_grays`** (an 11-step neutral ramp carrying the accent's
    hue, which that framework feeds to Background/Surface/Control per theme), is ported and tested
    but **not wired**: RinUI owns this app's neutrals, so using it would mean overriding RinUI's
    colour roles wholesale.
  - **What `accentForScheme(dark)` applies**, with shading on:

    | mode | accent |
    |---|---|
    | `default`, `custom` | the blend of the base — dark takes `secondary`, light `tertiary` |
    | `system`, Windows | **the OS's own accent for that scheme**, straight from the palette |
    | `system`, elsewhere | the blend, like the other modes |

    With shading off every mode uses its base verbatim in both schemes. The bases are:

    | mode | base |
    |---|---|
    | `system` | the OS *base* accent |
    | `custom` | the stored colour |
    | `default` | RinUI's own `#605ed2` |
  - **`system` can use the OS's tuned accents on Windows, and that is an option**
    (`appearance.accent_os_shading`, default on). The blends cannot reproduce them (table below), and
    Windows is the one platform that *has* a real answer, so the shell's own value can win over our
    derivation there. `_system_scheme_accent` is gated on `sys.platform == "win32"` rather than on
    "the palette provided something": elsewhere the palette's accent is not scheme-specific, or is
    not the user's theme colour at all. `default`/`custom` always blend — those are colours the OS
    knows nothing about. Three properties drive the settings row and are worth keeping in step:
    `accentOsShadingSupported` (this platform has OS accents at all — the row is **hidden**
    elsewhere, since it could never be turned on), `accentOsShadingAvailable` (it would take effect
    *now*: Windows **and** the system accent **and** shading on **and** both OS values captured —
    the row is disabled otherwise, and its description states the condition rather than leaving a
    dead switch looking broken), and `accentOsShading` itself (the stored preference, independent of
    availability).
  - **The `system` base is the OS *base* accent, not a scheme's variant** — deriving both variants
    from a colour already tuned for a scheme would tune it twice. `QPalette.Highlight` under the
    **dark** scheme is the base: verified against the OS on two accents, where it matched
    `DWM\AccentColor` (`0xAABBGGRR`) and differed from `Accent`, which carries the per-scheme value
    (`#1d6978` light / `#71d4db` dark for a teal base; `#0067c0` / `#4cc2ff` for blue).
    `_capture_system_accents()` reads all three values once at construction (dark scheme for
    `base` + `dark`, light scheme for `light`), then restores the scheme; it runs before the QML tree
    is loaded, so those switches are never visible.
    Falls back to the live palette when the platform cannot switch schemes, and to RinUI's colour
    when there is no palette at all (headless tests). `Explorer\Accent\AccentPalette` is *not* a
    usable source — it held oranges and a stray blue for both accents.
  - **How close each path gets to Windows, measured** (CIE Lab distance, two accents). `system` on
    Windows is *exact* by construction now (the OS's own numbers), so this table is about the blends
    — `default`/`custom`, and `system` off Windows:

    | accent | role | Windows | port | dE | earlier HSL family | dE |
    |---|---|---|---|---|---|---|
    | teal `#258292` | light | `#1d6978` | `#1c626e` | 3.4 | `#1d6978` | 0.0 |
    | teal | dark | `#71d4db` | `#5ca1ad` | **19.2** | `#3797aa` | 23.0 |
    | blue `#0078d4` | light | `#0067c0` | `#005a9f` | 12.5 | `#0067c0` | 0.0 |
    | blue | dark | `#4cc2ff` | `#409adf` | **16.6** | `#1a8ef3` | 32.5 |
    | | | | **51.7** | | | 55.5 |

    The port wins overall and by a lot on the dark variant. The old family's perfect light column
    was not a formula result: that version used the OS's *light-scheme* accent as its base, so light
    mode echoed the OS while its dark variant (HSL `+15 L / −10 S`) landed much further out. Trading
    that echo for deriving both variants from the true base is what improves the total — and it is
    the same trade that makes the behaviour identical off Windows.
  - Neither is exact, and a second accent shows why no formula over the base will be: Windows
    **preserves HSL saturation exactly** (teal `59.6 → 59.6`, blue `100 → 100` for its dark accent)
    where any blend towards white **desaturates** (teal's secondary falls to S 33.1), its dark accent
    sits at a **fixed lightness** of ~65% for both accents (`(max+min)/2` = 166.0 and 165.5 of 255),
    and its light accent follows no shared target, delta, ratio or contrast level (dL −6.7 vs −3.9).
    Reproducing it would mean fitting an undocumented rule to a couple of samples.
  - **That capture is re-entrant**: `setColorScheme` itself emits `paletteChanged`, which is what
    calls it back, so `_capturing_accents` guards it. `_on_palette_changed` re-captures (the OS
    accent can change at any time) and then emits `accentChanged`.
  - `appearance.accent_shading` (default **on**) is the switch, and it lives as a row *inside* the
    accent `SettingExpander` (`Shade per theme`, no icon) rather than as a card of its own: it only
    affects the accent. The row below it is the OS-finetuning option described above. Its setter emits `accentChanged` as well as `changed`, because turning it off
    changes the applied colour — that is what makes the window re-apply without a theme switch.
  - **The picked colour is written lazily.** A `ColorPicker` drag emits a change per mouse move, so
    `_set_custom_accent` stores the value in `_pending_accent` and restarts a 400 ms timer instead of
    writing the config each time; `_get_custom_accent` returns the pending value first, because
    reading straight from the store would show the last *persisted* colour and the swatch would snap
    back mid-drag. The accent still applies live — only the disk write waits. `_flush_pending_accent`
    is idempotent and runs on the timer. (A `QTimer` does not activate without an application, so the
    unit test asserts the pending value and calls the flush directly; that the timer really fires and
    coalesces is verified in the app — five rapid changes produced exactly one write.)
  - **The palette has exactly one consumer: the preview strip on the settings page.** RinUI exposes
    no accent-shade roles at all (no `Light1`/`Dark1` in either theme) and its controls draw
    hover/pressed states with `opacity` (`0.875` hover, `0.65`/`0.7` pressed on `Button`), so
    nothing else could read the variants. `accentPreview` hands the row either the trio (shading on
    — the OS's own light/base/dark in `system` mode on Windows, our blended trio otherwise) or the
    single flat colour (off) — which is precisely what the switch changes — and it
    follows the accent *in use*, not the stored custom colour the picker beside it edits.
  - The **preview strip** is **one fixed 84×26 rounded rectangle** beside the picker button, and
    deliberately **not a control**: no `TapHandler`, no tooltip. With shading on it is drawn as three
    segments, with shading off as a single field — the `Repeater` gives each segment `width / count`
    and rounds only the *outer* corners (`topLeftRadius` …), leaving the inner ones square so the
    segments read as one shape rather than three chips; the outline is a transparent `Rectangle` on
    top. Tokens rather than literals: `appearance.buttonRadius` (5) and `appearance.borderWidth` (1)
    with `controlBorderAccentColor`, so it reads as the surface of an accent-styled `Button`
    (`Button { highlighted: true }` in RinUI's gallery, the "Accent Style Button"). Per-corner radii
    need Qt 6.7+; they are also what avoids a `layer`/`OpacityMask` mask, which the HiDPI note warns
    about.
  - **The colour picker keeps its flyout but wears an icon.** `DropDownColorPicker` is wanted — it
    accepts any colour, which a preset list cannot — but its stock button draws the colour *inside
    itself*, so in the other accent modes (where it is disabled) the face would dim and recolour the
    very thing being previewed. Overriding its `contentItem` with an `Icon` keeps the flyout and the
    `color` aliases while leaving the colour to the strip beside it. Its `implicitWidth` binding reads
    an id inside that replaced contentItem, so the instance sets `implicitWidth` explicitly.
- The settings page's content lives in a `Flickable` (with an AsNeeded `ScrollBar`) because the page
  is taller than a short window. Keep new rows inside that column — giving the content
  `anchors.fill: parent` again would silently disable scrolling, and the numbers to watch are
  `contentHeight` vs the viewport height. The **Flickable fills the whole page and the 24px inset
  lives on the column** (`qml/pages/SettingsPage.qml`), which is RinUI's own `FluentPage`
  arrangement: RinUI's `components/ScrollBar.qml` anchors this bar to `parent.right` /
  `parent.verticalCenter`, so it inherits whatever inset its Flickable has — margins on the
  Flickable strand the bar in the page gutter, 24px from the content edge instead of hugging it.
  `contentHeight` carries one extra inset (`+ 48`) so the last card clears the bottom edge.
- **Typography** (`fonts.*`) is three faces, all applied live:
  - **Code** (`code_family`/`code_size`): the expression surfaces — the calculator's two inputs
    and its outcome line, the Variables table cells, the History card lines
    and the Log pane. Size defaults to 14.
  - **Keyboard** (`keyboard_family`/`keyboard_size`): the on-screen keys; 16 by default, because the
    math glyphs (∞ √ ∛ ≤ ≥) are the content there. A serif face is recommended and is the default:
    Cambria covers every glyph the shipped layout uses, where Georgia and Times New Roman lack `∛`.
  - **LaTeX** (`latex_font`/`latex_size`): rendered results. `latex_size` defaults to ziamath's own
    24 pt.
  - Each row is a **`SettingExpander`, not a `SettingCard`**: the size `SpinBox` sits in the header
    (compact, always visible, like the accent row's mode combo) and the family control lives in the
    collapsible body with the full card width — a preference list and a spinner side by side left the
    list showing only its tail. The body's `SettingItem` description also reports what the chain
    resolves to ("Starts with X, then N fallback(s)") and any glyph no family in it can draw, neither
    of which is visible from the candidate list.
- **Font fallback is a real Qt feature, and the app uses it — but not through QML's `font` group.**
  Qt resolves each character against an ordered family list (`QFont.setFamilies`), so a glyph the
  first face lacks is drawn from the next one that has it. Two consequences shape the code:
  - **QML cannot express that list.** Its `font` value type has only a single `family` (there is no
    `families`), and assigning `"Arial, NoSuchFont"` to `font.family` is treated as *one literal
    name* — it silently renders in the default font. So `SettingsViewModel` builds the font in
    Python and exposes it as a `QFont` property: pages bind `font: settingsVM.codeFont` /
    `settingsVM.keyboardFont` and get real per-character fallback. Verified by rasterising the same
    glyph two ways: `∛` under `["Consolas","Cambria"]` is pixel-identical to `["Cambria"]`, while
    `∞` (which Consolas has) stays Consolas.
  - **The row stores a preference list, and it is passed through in full.** `fonts.code_family` /
    `fonts.keyboard_family` are comma-separated; generic keywords (`serif`, `monospace`,
    `sans-serif`) are first expanded into real family names, because `"monospace"` is not something
    Qt can look up. Names are de-duplicated but never reordered or dropped: an uninstalled name is
    simply skipped during lookup, and an earlier face is *not* replaced by a later one that draws
    more — the list is the user's stated order.
  - **Coverage is reported per chain, not per family.** A glyph is only a problem when *no* family
    in the list can draw it, which is the case Qt cannot rescue; that is what
    `codeMissingGlyphs` / `keyboardMissingGlyphs` show, alongside `*FallbackCount` ("then 2
    fallbacks"). The measurement uses `QRawFont.glyphIndexesForString` (glyph 0 = `.notdef`), cached
    per family. The obvious `QFontMetrics.inFont()` is **unusable**: it answers `True` for every
    character of every family (Qt's substitution hides the gap), so it would report full coverage
    for a face that draws tofu. `python/fonts.py` holds only the *file-level* truth (fontTools, for
    ziamath); the Qt-side check lives in the viewmodel, keeping the model layer Qt-free.
  - **A font that claims coverage gets no fallback.** Qt falls back only when the earlier face
    *reports* it lacks the glyph. A broken or odd font can therefore defeat the chain: the installed
    `Fixedsys` is a bitmap face DirectWrite refuses to load (`CreateFontFaceFromHDC() failed`), yet
    Qt reports `QFontInfo(...).exactMatch() is True` and returns non-zero glyph indices for
    practically every character — so `Fixedsys, Cambria` renders in the mangled Fixedsys stand-in and
    never reaches Cambria, while `Consolas, Cambria` does fall back for `∛`. There is no reliable
    signal to detect this from the app side (the substitution looks successful), so the honest
    behaviour is to pass the list through and let Qt decide; the fix for such a case is to order the
    list differently (put the working font first) rather than to trust the first name.
  - `QFontInfo(font).exactMatch()` is False (and `family()` becomes the substitute, e.g. `Tahoma`)
    when Qt *cannot* resolve a family at all — the case that is detectable.
  - The required glyph set is **derived from the layout** (`keyboard_config.label_glyphs`) and from
    `fonts.CODE_GLYPHS`, so adding a key with a new glyph automatically adds it to the requirement.
  - `QFontDatabase.families()` **aborts the process** when there is no `QGuiApplication` (it does not
    raise), so the display-name resolution returns the first name unchanged when
    `QGuiApplication.instance()` is None — that is what keeps the settings viewmodel usable headless
    in tests. The coverage rules themselves need a real application, so they are tested in a
    subprocess.
- **Text cursors: the blocker is RinUI's `Expander`, not the controls.** Everything inside a
  `SettingExpander` shows an arrow no matter what the control does, because `Expander.qml` lays this
  over the whole expander:

  ```qml
  MouseArea { z: 999; anchors.fill: parent; enabled: !root.enabled
              hoverEnabled: false; preventStealing: true; onClicked: {} }
  ```

  It declares **no `cursorShape`**, so it resolves to Arrow, and at `z: 999` it is the topmost
  cursor-bearing item under the pointer — Qt takes the cursor from *that*, not from the control
  below. The control still receives hover (`containsMouse` is true, tooltips work); only the cursor
  is lost, which is what makes this so easy to misdiagnose. `SettingsPage` fixes it by showing the
  blocker only while it actually blocks (`visible: blocker.enabled`, i.e. only when the expander is
  disabled — its `enabled` is `!expander.enabled`), which leaves that behaviour intact and lets the
  controls' own cursors through. That fix lives in the two components that wrap the bases
  (**`ExpanderRow`** for `SettingExpander` — what settings rows must use — and **`ExpanderPanel`**
  for the plain `Expander`): it is applied by each instance as it is created, so it also covers
  expanders built at runtime and expanders on any page — a page-level sweep would miss both
  (verified: an `ExpanderRow` and a RinUI `SettingExpander` created side by side after load differ,
  text cursor vs arrow, and the same holds for `ExpanderPanel` against a bare `Expander`).
  **Do not "fix" this per control**: adding `cursorShape` MouseAreas
  over the fields does nothing while the blocker is up, and once it is gone they are dead weight —
  RinUI's `TextField`/`TextArea`/`SpinBox` already carry the right cursors (the text areas say
  `IBeamCursor`, the SpinBox's steppers stay Arrow), and Qt resolves item cursors **without** needing
  `hoverEnabled` on them.
  - Verified with the real OS cursor (`GetCursorInfo`), not with a QML model of the hit test:
    `Window.cursor()` does **not** track item cursors in a RinUI window, so reading it proves
    nothing. A `Item.childAt` descent is likewise misleading. The reliable recipe is: raise the
    window and confirm it is *the foreground window* (`GetForegroundWindow` after `AttachThreadInput`,
    since Windows' foreground lock refuses a plain `SetForegroundWindow`), park the mouse with
    `QCursor.setPos`, and compare against controls of known cursor. Without the foreground check
    every reading comes back Arrow and looks like a real failure.
- **Only some rows can be restyled by assigning `font.*`.** RinUI draws several labels with its own
  hardcoded `typography: Typography.Body` (whose family is `Utils.fontFamily`), so a `font.family`
  on the control never reaches the glyphs — the rendered text keeps the UI font while the *control*
  reports the new one, which is easy to mistake for "it worked". The keyboard keys and the Variables
  table cells therefore **replace `contentItem`** with a `Text` carrying the code/keyboard font. When
  overriding a RinUI delegate's `contentItem`, keep `visible: !<delegate>.editing` (otherwise the
  label draws on top of the open inline editor) and mirror the original margins. The Variables
  *inline editor* itself still uses QQC2's default edit delegate, so it edits in the UI font.
- **ziamath takes a font FILE with an OpenType `MATH` table, not a family** — and it fails outright
  rather than substituting: a font without one raises `ValueError: Font has no MATH table!`, and a
  collection (`.ttc`) raises `UnicodeDecodeError` because ziafont parses the file as a single font.
  Hence the LaTeX font row is a **dropdown of what can actually render**, not a text box:
  `python/fonts.py` scans the platform font directories, keeps only fonts with a MATH table (via
  fontTools' table directory), caches the result, and extracts the subfont of a `.ttc` into a scratch
  `.ttf` on first use — without that, Windows' only system math font (Cambria Math, shipped inside
  `cambria.ttc`) would be unusable and the list would hold nothing but the default. Choice 0 is
  always `""` = ziamath's bundled STIX Two Math, which needs no system font; `math_font_path()`
  returns None for it and for any unknown name. Scanning is lazy: with the default (no system font
  chosen) nothing is scanned. The resolved path reaches the renderers via
  `CalculatorViewModel.set_latex_font` / `HistoryModel.set_latex_font`, mirroring
  `set_latex_size`, and `MainViewModel` re-applies it on every `changed` (a path is not a family
  name, so the family changing is not the only way it can move).
- `fonts.latex_size` reaches the renderers via `CalculatorViewModel.set_latex_size` /
  `HistoryModel.set_latex_size` (mirroring `set_latex_color`), applied by `MainViewModel` at startup.
- Window geometry is remembered when `window.remember` is on: the **size** is supplied declaratively
  by `MainWindow.qml` (`settingsVM.startupWidth`/`startupHeight`, clamped to the primary screen), the
  **position** is applied by the viewmodel only if it still falls on a connected screen — and not at
  all when the remembered state is maximized, where the platform places the window so that dragging
  it out of fullscreen lands where the system put it — and the **maximized** state is applied once the
  window is shown. Changes are debounced (500 ms) and flushed on close. Never resize the window from
  the viewmodel at startup — see the trap list.

## Building (Windows, Nuitka)

`uv run python scripts/build_windows.py` → `build/main.dist/symplify.exe`
(standalone dir, MSVC, no console window). Needs Visual Studio Build Tools locally; CI runs it.
The script is two steps: the Nuitka run, then `prune_qt`. Nuitka's PySide6 plugin bundles *every* Qt
module it can find, where the app loads 23 of them — QtWebEngineCore alone was 205 MB of the 513 MB
dist. `--prune-only` re-runs just the second step against an existing `build/main.dist/` (no
rebuild), which is how a wrong list gets corrected without a second compile.

**Both Qt lists are evidence-backed — keep them that way when you touch them:**

- `KEEP_QT_DLLS` is exactly what a started `build/main.dist/symplify.exe` has mapped
  (`(Get-Process symplify).Modules`). Counter-intuitive but real: `qt6pdf.dll` and
  `qt6shadertools.dll` *are* loaded (the Qt Quick Controls stack pulls them in), and the Basic style
  runs alongside `qt6quickcontrols2fusion.dll` + `…windowsstyleimpl.dll`.
- `PRUNE_QML_DIRS` is the QML nothing reaches, checked with the `import` closure of the app's and
  RinUI's files. Two edges worth remembering: `QtQuick/NativeStyle` is **kept** although no app QML
  names it (QtQuick/Controls/Windows — 38 files — imports it), and `QtMultimedia` /
  `Qt.labs.folderlistmodel` are reached *only* from QtQuick/VirtualKeyboard and QtQuick/Dialogs,
  which are themselves pruned.
- After a prune, re-check that every `import` in every remaining `.qml` resolves to a directory that
  still exists — that is what catches a style variant referencing a pruned style (QtQuick/Pdf's
  `+Material`/`+Universal` variants were doing exactly that).
- The DLLs come from the venv (`.venv/Lib/site-packages/PySide6/Qt6*.dll`), so a wrongly pruned one
  can be copied back and `--prune-only` re-run — no rebuild.

`cleanup_rinui_dir()` runs after every build, and exists because Nuitka **imports** RinUI while
analysing the program — that import sits outside `prepare()`, so the build makes RinUI drop
`<root>/RinUI/config/rin_ui.json` in the project: exactly the directory invariant 8 keeps away at
runtime, arriving through the build instead.

`--lto=no`: the `/GL` + `/LTCG` link is single-threaded and a large slice of the build for no
measurable runtime gain in a calculator. Measured on the dev machine: ~11 min per build, dist 266 MB
(was 513 MB).

Data-file pitfalls for frozen builds (update this list when you add data-reading deps):

- `ziamath` / `ziafont` fonts, `latex2mathml/unimathsymbols.txt`, RinUI's whole QML tree,
  `python/keyboard_config.yaml` and `fontTools` (read by `python/fonts.py` to inspect installed
  fonts) must be included via the `--include-*` flags in `scripts/build_windows.py`.
- Packages whose data is loaded through `importlib.resources` by name
  (e.g. `ziamath.fonts`) need `--include-module=<subpackage>` — Nuitka can't follow string refs.
- Debugging a GUI exe that exits early: rebuild with `--windows-console-mode=force` to see the traceback.

## Versioning

- **SemVer**; canonical value in `pyproject.toml`, runtime copy `python/version.py`, shown in About
  via the `appVersion` context property.
- `python/version.py` is **rewritten wholesale** by `scripts/release.py` — never add code to it, the
  next release bump would erase it.
- Third-party versions in About must never be hardcoded: RinUI comes from the `rinuiVersion` context
  property (`RinUI.__version__`) and Qt from `qtVersion` (`PySide6.QtCore.qVersion()`), both
  registered in `main.py`. Do **not** reach for `importlib.metadata` (a frozen build ships no
  `.dist-info`, so it raises) or for Qt's QML global `qtRuntimeVersionString` — that global does not
  exist under PySide6, so a `typeof` guard around it silently drops the Qt version forever.
- Change it with `scripts/release.py` (patch|minor|major|explicit [+ `--tag`]) — it syncs both files
  and, with `--tag`, commits and tags `vX.Y.Z`.
- Pushing a `vX.Y.Z` tag runs the Windows packaging workflow and uploads the `.dist` artifact.

## History of routes (read-only branches)

- `main` — RinUI + PySide6/QML (current)
- `v3-fluentwinui3-qml` — third route, FluentWinUI3-styled QML
- `v1-qfluentwidget`, `v2-qfluentwidget` — early QWidget (qfluentwidgets) prototypes

## Testing

`tests/` holds the behaviour contract — plain asserts plus a runner, no test framework needed (the
files are also pytest-compatible if one is ever added). One command runs everything:

```bash
uv run python -m tests                # every module
uv run python -m tests.test_model     # model + viewmodels
uv run python -m tests.test_settings  # settings store, config paths, RinUI bootstrap
```

`test_model.py` locks the deliberate permissiveness (unknown symbols stay symbolic, `2x`, `x^2`,
shadowing a sympy name) **and** the rules that were hard-won (unknown calls are reported, augmented
assignment needs an existing target, a rejected write leaves no variable behind). **Run it before
and after touching `calculator.py` or the write path** — the parser transformations are user-visible
behaviour, and a "harmless" transform swap can change parsing across the whole app
(`implicit_multiplication_application` turns `foo(1)` into `f*o**2`).

`test_settings.py` runs the config-directory rules against injected environments and temporary
directories (the real user config is never touched), and runs the RinUI bootstrap in a **subprocess**
(its effect is import-time, so it needs a fresh interpreter): no `./RinUI/`, values migrated, writes
disabled.

When changing QML pages, a short manual/app-launch check plus scanning the startup console for QML
warnings is still the baseline; GUI smoke scripts stay throwaway (kept out of git). Remember the
model layer itself needs no Qt at all: `MainViewModel(store)` round-trips in a bare `python -c`.
