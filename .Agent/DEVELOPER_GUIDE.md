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
  settings.py                   # Settings store: config dir resolution (portable data/ or the
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
    settings_viewmodel.py       #   Settings: appearance/typography/window, config path, the only writer
    log_viewmodel.py            #   LogViewModel (formattedLogs)
  accent.py                     # WinUI-style accent shading (HSL shade family, zero Qt)
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
                                #   ExpanderRow / ExpanderPanel (RinUI expanders that keep
                                #     their content's text cursors),
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
  The font size comes from the settings page (`fonts.latex_size`), the colour from the theme.
- History renders each entry's LaTeX **lazily per visible row** and caches sizes; after lazy render
  the model emits `dataChanged` for the LaTeX/natural-size roles so the open delegate refreshes.
- Long results/text use `elide: ElideRight` (mono lines in history align the result `=` under the
  assignment operator via `" ".repeat(name.length + 1)`).

## Settings & config

- One YAML file, written **only** by `SettingsViewModel` (invariant 8). The schema, defaults and
  validation live in `python/settings.py` (`DEFAULTS`): unknown keys survive a rewrite, invalid
  values fall back or clamp, writes are atomic (temp file + `os.replace`), and a read-only location
  degrades to in-memory values with a warning the page displays. Keys:
  `appearance.theme|backdrop|accent|accent_mode|accent_shading|accent_os_shading`,
  `fonts.code_family|code_size|keyboard_family|keyboard_size|latex_font|latex_size`,
  `window.remember|width|height|x|y|maximized`. The page groups them under the subtitles
  **Interface / Typography / Language / Settings file / About**. Layout follows RinUI's own gallery
  (`examples/pages/Settings.qml`): a section is a `ColumnLayout { spacing: 3 }` holding a
  **`Typography.BodyStrong`** subtitle and then one card per row, and the sections are separated by
  the outer column's spacing. Subtitle size is the gallery's, not a guess — `BodyStrong` renders at
  the theme's `bodyStrongSize` (14 pt, weight 600), i.e. *the same size as a card title but bolder*;
  `Typography.Subtitle` (20 pt) is one size too large and reads as a second page heading. Most rows
  are `SettingCard`s; a `SettingExpander` is used only where a row carries a second row of its own
  (the accent and About groups). `fonts.latex_size` used to be `rendering.latex_size`: `load()`
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
    and its result line, the LaTeX fallback text, the Variables table cells, the History card lines
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
(standalone dir, MSVC, LTO, no console window). Needs Visual Studio Build Tools locally; CI runs it.

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
