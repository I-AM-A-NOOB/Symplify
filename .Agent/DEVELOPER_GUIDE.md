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
  settings.py                   # Settings store: config dir resolution (portable Data/ or the
                                # OS convention), atomic YAML read/write, validation. Zero Qt.
  rinui_bootstrap.py            # Takes RinUI's own config directory over and injects our
                                # settings; `prepare(ROOT)` is the ONLY way to import RinUI.
  viewmodel/                    # Qt bridge (QObject + models). The ONLY layer that imports Qt
                                # (besides main.py). State that must survive page switches lives here.
    input_mode.py               #   InputMode (CODE=0 / ASSIGN=1) — UI state, not model state
    main_viewmodel.py           #   Root VM; aggregates children; signals sendToCode/sendToAssign
    calculator_viewmodel.py     #   Result state, LaTeX data-URL, input persistence, clear_result
    variables_viewmodel.py      #   VariablesModel (3-col: name/expr/type) + CRUD + Qt edit protocol
    history_viewmodel.py        #   HistoryModel (QAbstractListModel, newest first, lazy LaTeX)
    search.py                   #   SearchFilterModel + Variables/HistoryFilterModel: the pages'
                                #   search boxes (proxy over the models above)
    settings_viewmodel.py       #   Settings: appearance/rendering/window, config path, the only writer
    log_viewmodel.py            #   LogViewModel (formattedLogs)
  latex_render.py               # latex_to_svg(latex, size=, color=) + svg_size — theme-aware ziamath
  keyboard_config.py            # YAML keyboard layout -> tabs
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
                                #   HScrollView, LatexImage, KeyboardPanel, SearchBar,
                                #   SegmentedItem/SelectorBarItem (focus-indicator shadows)
docs/
  architecture.md               # Model-first walkthrough: the two requests, the data flow
                                # (sources in, sinks out), the write path and the error kinds;
                                # architecture.svg = layer map
scripts/
  build_windows.py              # Nuitka standalone build
  release.py                    # SemVer bump (pyproject + python/version.py), optional tag
  cheat-sheet.md                # Human quick reference
.github/workflows/build-windows.yml  # Builds on windows-latest for tags v* / manual runs
```

## Core rules & invariants

1. **`python/model/` never imports Qt**, and it is the **only** place that decides what an input
   *means* (syntax, name resolution, failure kinds). Two requests exist — `evaluate` for a read and
   `assign(Assignment, ...)` for a write — both returning `Success | Failure`. Never assemble an
   expression string in a ViewModel (that is how `x += 1` used to become the self-referential
   `x = x + 1`), and never re-implement name rules outside `validate_name` / `is_sympy_name`.
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
   the location (portable `<root>/Data/config.yaml` if that folder exists, else the OS config
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
  most pin a few to `Position.Bottom`.- RinUI's `ToolTip`, `Menu`, `Dialog` are QQC2 subclasses used as **child elements** (not attached
  property syntax). Adding children of a RinUI control may fight its internal state overrides
  (e.g. disabled-state opacity) — prefer real child layout instead of `enabled` toggles.
- Merely *instantiating* `RinUI.Dialog` logs two `TypeError: Cannot read property
  'width'/'height' of null` warnings from RinUI's own `Dialog.qml` (lines 21/23) while it binds
  before being shown. Harmless and pre-existing — don't chase it; it is not a page bug.
  `Slider` and the colour pickers do the same on construction, which is why the accent colour uses a
  preset `ComboBox` rather than `DropDownColorPicker`.
- **RinUI creates its own config directory at import time**: `RinUI/core/config.py` computes
  `BASE_DIR = Path.cwd()` and writes `<cwd>/RinUI/config/rin_ui.json` when it is missing, with no
  supported way to redirect or disable it (verified against 0.4.4.1). `python/rinui_bootstrap.py`
  takes that location over — read its module docstring before touching it — and the consequences are
  an invariant: it is why `import RinUI` must never happen at module level in app code, and why
  `main.py` gets `RinUIWindow` from `prepare()` instead of from `RinUI`.
- **SettingCard / SettingExpander API quirks** (the published docs describe a newer version than the
  installed one): the icon is set with `icon.name:` — assigning `icon:` fails with "read-only
  property"; a `SettingCard`'s bare children land in its **right-hand** slot, while a
  `SettingExpander`'s bare children are its **collapsible content** and should be `SettingItem`s
  (`content:`/`action:` on it go to the header's right slot instead); `SettingItem` has **no**
  `content` property; and RinUI has no `RadioButtons` (use `Segmented` or a `ComboBox`).
- **Never resize a RinUI window while it is being created and then maximize it.** The window fills
  the screen but its content stays drawn in the pre-resize rectangle, surrounded by a white border,
  and later resizes never repair it — while Qt reports the correct window state *and* content size,
  so the desync is purely in the presentation layer (Mica / DWM). Observed fixes and their reasons:
  the remembered **size** is set declaratively in `MainWindow.qml`
  (`width: settingsVM.startupWidth`), so the window is created at the right size and never resized;
  the **position** is applied after creation (a move is safe); and the **maximized** state uses
  `showMaximized()` once the window is visible, because maximizing before it is shown has the same
  stale effect (as does `setWindowState(WindowMaximized)` afterwards). Verified against RinUI 0.4.4.1
  on Windows 11 — when touching window geometry, check it visually, Qt values can look perfect.
- **A bare `QQuickView` can hang on components that touch the `Theme` singleton** — `Expander`
  (hence `SettingExpander`) spins forever during construction when the engine has no `ThemeManager`
  context property, instead of merely warning like the other singleton uses. The app is fine
  (`RinUIWindow` registers it, and can host the settings page); a throwaway probe must either
  register a `ThemeManager` or load the page through `RinUIWindow`.

## Rendering / display

- LaTeX: `Success.latex` (`Calculator.render_latex`, sympy) → VM builds a percent-encoded SVG
  **data URL** (`latex_render.latex_to_svg`, with `size=`/`color=`), `svg_size` for natural size;
  `LatexImage` (qml/components) renders crisp by scaling `sourceSize` by `devicePixelRatio`.
  The font size comes from the settings page (`rendering.latex_size`), the colour from the theme.
- History renders each entry's LaTeX **lazily per visible row** and caches sizes; after lazy render
  the model emits `dataChanged` for the LaTeX/natural-size roles so the open delegate refreshes.
- Long results/text use `elide: ElideRight` (mono lines in history align the result `=` under the
  assignment operator via `" ".repeat(name.length + 1)`).

## Settings & config

- One YAML file, written **only** by `SettingsViewModel` (invariant 8). The schema, defaults and
  validation live in `python/settings.py` (`DEFAULTS`): unknown keys survive a rewrite, invalid
  values fall back or clamp, writes are atomic (temp file + `os.replace`), and a read-only location
  degrades to in-memory values with a warning the page displays. Keys:
  `appearance.theme|backdrop|accent`, `rendering.latex_size`,
  `window.remember|width|height|x|y|maximized`.
- **Location**: `<root>/Data/config.yaml` when a `Data` folder sits next to the app (portable mode;
  `root` is the exe directory when frozen and the repository root in dev), otherwise the OS
  convention — `%APPDATA%\Symplify\` (Windows, falls back to `%LOCALAPPDATA%`),
  `$XDG_CONFIG_HOME/symplify/` (Linux, falls back to `~/.config/symplify/`),
  `~/Library/Application Support/Symplify/` (macOS). The settings page shows the resolved path and
  mode, and clicking that row opens the folder.
- Appearance is applied through RinUI's `ThemeManager` (the QML `Theme` singleton wraps it), injected
  before the window exists so the first frame is already themed. The **accent colour is the
  exception**: RinUI's Python `set_theme_color` only persists the value — what actually re-colours the
  controls is `Utils.primaryColor`, which its QML `Theme.setThemeColor` sets as well. So the viewmodel
  stores the accent and emits `accentChanged`, and `SettingsPage.qml` applies it. Theme and backdrop
  apply fine through the Python slots.
- The settings page's content lives in a `Flickable` (with an AsNeeded `ScrollBar`) because the page
  is taller than a short window. Keep new rows inside that column — giving the content
  `anchors.fill: parent` again would silently disable scrolling, and the numbers to watch are
  `contentHeight` vs the viewport height. `rendering.latex_size` reaches the
  renderers via `CalculatorViewModel.set_latex_size` / `HistoryModel.set_latex_size` (mirroring
  `set_latex_color`), applied by `MainViewModel` at startup.
- Window geometry is remembered when `window.remember` is on: the **size** is supplied declaratively
  by `MainWindow.qml` (`settingsVM.startupWidth`/`startupHeight`, clamped to the primary screen), the
  **position** is applied by the viewmodel only if it still falls on a connected screen, and the
  **maximized** state is applied once the window is shown. Changes are debounced (500 ms) and flushed
  on close. Never resize the window from the viewmodel at startup — see the trap list.

## Building (Windows, Nuitka)

`uv run python scripts/build_windows.py` → `build/main.dist/symplify.exe`
(standalone dir, MSVC, LTO, no console window). Needs Visual Studio Build Tools locally; CI runs it.

Data-file pitfalls for frozen builds (update this list when you add data-reading deps):

- `ziamath` / `ziafont` fonts, `latex2mathml/unimathsymbols.txt`, RinUI's whole QML tree,
  and `python/keyboard_config.yaml` must be included via the `--include-*` flags in
  `scripts/build_windows.py`.
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
