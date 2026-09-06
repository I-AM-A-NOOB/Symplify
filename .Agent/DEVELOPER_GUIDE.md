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
  model/                        # PURE PYTHON, must never import Qt.
    calculator.py               #   Calculator.evaluate(expr, variables) -> CalculationResult
    variable.py                 #   VariableManager (VariableEntry snapshots) + classify_type
    input_mode.py               #   InputMode (CODE=0 / ASSIGN=1)
  viewmodel/                    # Qt bridge (QObject + models). The ONLY layer that imports Qt
                                # (besides main.py). State that must survive page switches lives here.
    main_viewmodel.py           #   Root VM; aggregates children; signals sendToCode/sendToAssign
    calculator_viewmodel.py     #   Result state, LaTeX data-URL, input persistence, clear_result
    variables_viewmodel.py      #   VariablesModel (3-col: name/expr/type) + CRUD + Qt edit protocol
    history_viewmodel.py        #   HistoryModel (QAbstractListModel, newest first, lazy LaTeX)
    log_viewmodel.py            #   LogViewModel (formattedLogs)
  latex_render.py               # latex_to_svg(latex, color=) + svg_size — theme-aware ziamath
  keyboard_config.py            # YAML keyboard layout -> tabs
  version.py                    # Runtime version copy (kept in sync with pyproject)
qml/
  MainWindow.qml                # FluentWindow + navigationItems (middle items + Log/Settings
                                # pinned bottom; do NOT give items position:Top — RinUI caps that
                                # section at 20% height and it scrolls/splits badly on short windows)
  pages/                        # Calculator / Variables / History / Log / Settings
  components/                   # Reusable pieces (+ qmldir):
                                #   HScrollView, LatexImage, KeyboardPanel,
                                #   SegmentedItem/SelectorBarItem (focus-indicator shadows)
scripts/
  build_windows.py              # Nuitka standalone build
  release.py                    # SemVer bump (pyproject + python/version.py), optional tag
  cheat-sheet.md                # Human quick reference
.github/workflows/build-windows.yml  # Builds on windows-latest for tags v* / manual runs
```

## Core rules & invariants

1. **`python/model/` never imports Qt.** UI calls cross a ViewModel first.
2. **RinUI's NavigationView destroys & recreates pages on every navigation.**
   Anything that must survive switching pages lives in a ViewModel, not QML page state.
   The Calculator page pattern: VM is the single source of truth; the Segmented control
   initializes from the VM in `Component.onCompleted` and only writes back from user
   clicks (`onClicked`) — never from `onCurrentIndexChanged` during page init (that resets
   the mode). This has regressed twice; keep the pattern.
3. **Context properties** (registered in `main.py`): `vm`, `appVersion`, `calcVM`, `varsVM`,
   `variablesModel`, `historyVM`, `logVM`, `keyboardTabs`.
4. **Keyboard panel keys & its SelectorBar tabs use `focusPolicy: Qt.NoFocus`** so typing stays
   in the focused input. Everywhere else leave focus policy at defaults (focus ring + Ctrl+Tab).
5. **LaTeX is theme-aware**: render with `latex_to_svg(..., color=...)`; when the RinUI theme
   changes, QML (Calculator/History pages) calls `calcVM.set_latex_color` / `historyVM.set_latex_color`.
6. **Input persistence**: `calcVM.inputText / assignName / assignOperator / assignValue` persist
   across page switches.

## Known RinUI / Qt traps (learned the hard way)

- Import **unversioned** `QtQuick` (`import QtQuick`) where you need current API — `import QtQuick 2.15`
  version-gates newer members (e.g. `currentRow`, `itemAtCell` revisions).
- RinUI's experimental `TableView` sets `acceptedButtons: Qt.NoButton`, which kills its built-in
  edit triggers; the Variables page overrides it back to `Qt.LeftButton` and wires real editing
  (`flags()` `ItemIsEditable` + `model.setData`). Its `itemAtCell(a, b)` is `(column, row)`.
- RinUI caps Top/Bottom nav sections at 20% height → keep main items unpositioned (middle) and at
  most pin a few to `Position.Bottom`.
- RinUI's `ToolTip`, `Menu`, `Dialog` are QQC2 subclasses used as **child elements** (not attached
  property syntax). Adding children of a RinUI control may fight its internal state overrides
  (e.g. disabled-state opacity) — prefer real child layout instead of `enabled` toggles.

## Rendering / display

- LaTeX: `CalculationResult.latex` (sympy) → VM builds a percent-encoded SVG **data URL**
  (`latex_render.latex_to_svg`), `svg_size` for natural size; `LatexImage` (qml/components) renders
  crisp by scaling `sourceSize` by `devicePixelRatio`.
- History renders each entry's LaTeX **lazily per visible row** and caches sizes; after lazy render
  the model emits `dataChanged` for the LaTeX/natural-size roles so the open delegate refreshes.
- Long results/text use `elide: ElideRight` (mono lines in history align the result `=` under the
  assignment operator via `" ".repeat(name.length + 1)`).

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
- Change it with `scripts/release.py` (patch|minor|major|explicit [+ `--tag`]) — it syncs both files
  and, with `--tag`, commits and tags `vX.Y.Z`.
- Pushing a `vX.Y.Z` tag runs the Windows packaging workflow and uploads the `.dist` artifact.

## History of routes (read-only branches)

- `main` — RinUI + PySide6/QML (current)
- `v3-fluentwinui3-qml` — third route, FluentWinUI3-styled QML
- `v1-qfluentwidget`, `v2-qfluentwidget` — early QWidget (qfluentwidgets) prototypes

## Testing

The `python/model` layer is pure Python — headless sanity is trivial
(`MainViewModel` round-trips in a bare `python -c`). GUI smoke scripts are throwaway
(kept out of git); don't rely on them. When changing QML pages, a short manual/app-launch check
plus checking the app's startup console output for QML warnings is the baseline.
