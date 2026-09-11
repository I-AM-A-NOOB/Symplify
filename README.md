<p align="center">
  <h1 align="center">Symplify</h1>
  <p align="center">A Modern Symbolic Calculator Built with SymPy + PySide6</p>
</p>

---

Symplify is a graphical symbolic calculator that wraps SymPy's powerful CAS (Computer Algebra System) in a clean, Fluent-styled desktop UI. The interface is written in **QML (Qt Quick Controls)** using the [RinUI](https://github.com/RinLit-233-shiroko/Rin-UI) component library, with business logic kept in a pure-Python **MVVM** core that has zero Qt dependencies.

> **Status:** The calculator, variables, history and theme settings are functional; the plotting area is still a placeholder (see [Roadmap](#roadmap)).

## Features

- **Symbolic & Numeric Computation** — Derivatives, integrals, limits, equation solving, matrix algebra, and more via SymPy. Results are shown both as SymPy text and rendered $\LaTeX$.
- **Dual Input Modes** — Toggle between **Code** (evaluate any expression) and **Assign** (variable assignment with dedicated name/operator/value fields, including `+=`, `-=`, `*=`, `/=`). The mode and inputs survive page switches.
- **Theme-Aware $\LaTeX$** — Results are rendered via `ziamath` at screen DPI and re-tinted automatically when the app theme changes.
- **Variable Management** — Snapshot entries (name / expression / type). Invalid expressions are kept in the list as `NaN` rows instead of being dropped; double-click a cell to edit inline.
- **Keyboard Panel** — On-screen math keyboard with smart cursor positioning for Greek letters, operators and functions (7 tabs, YAML-configurable).
- **History Cards** — Newest-first cards with rendered $\LaTeX$, timestamps, a context menu (copy value/result, copy $\LaTeX$), and *Send to input* to restore any entry in the calculator. Failed calculations are kept as error cards too (the reason shown in red), so a broken expression can be sent back and corrected.
- **Live Search** — Both the History and Variables pages have a search box with a switchable match mode (History: fuzzy / expression / result; Variables: fuzzy / name / value / type). Typing is debounced; clearing the box restores every entry.
- **Persistent Settings** — Theme, backdrop, accent colour, result font size and window geometry live in one YAML file. It goes in the OS config directory (`%APPDATA%\Symplify\` on Windows, `$XDG_CONFIG_HOME/symplify/` on Linux, `~/Library/Application Support/Symplify/` on macOS) — or next to the app in `Data/config.yaml` when that folder exists, which makes the whole thing portable.
- **Focus Navigation** — `Ctrl+Tab` / `Ctrl+Shift+Tab` cycle focus through the UI; `Ctrl+Return` calculates.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation & Run

```bash
git clone https://github.com/I-AM-A-NOOB/Symplify.git
cd Symplify

uv sync          # or: pip install -e .
python main.py
```

### Windows packaging (Nuitka)

Build a standalone directory with MSVC (needs Visual Studio Build Tools):

```bash
uv sync
uv run python scripts/build_windows.py   # -> build/main.dist/symplify.exe
```

A GitHub Actions workflow (`.github/workflows/build-windows.yml`) produces the
same artifact on `windows-latest` — trigger it manually or on a `v*` tag push.

### Releases & versioning

Symplify follows [SemVer](https://semver.org). The version lives in
`pyproject.toml` (canonical) with a runtime copy in `python/version.py`; the
About page reads it via the `appVersion` context property. Bump and tag with:

```bash
uv run python scripts/release.py minor          # 0.1.0 -> 0.2.0
uv run python scripts/release.py minor --tag    # also commit + tag v0.2.0
```

Tags named `vX.Y.Z` trigger the Windows packaging workflow, so the release
flow is: bump → tag → CI builds and uploads `symplify.exe`.

## Architecture

Symplify follows **MVVM**. The `python/` package is split into layers; the model is pure Python with no Qt imports, which keeps it unit-testable and independent of any UI framework.

![Architecture diagram, model-focused](docs/architecture.svg)

- **Model** (`python/model/`) — Pure business logic, and the only place that decides what an input *means*. `Calculator` answers two requests — `evaluate(expression, scope)` for a read and `assign(Assignment, scope)` for a write — returning a `Success` (value + LaTeX) or a `Failure` (kind + message + hint); it also audits unknown function calls and classifies errors. `VariableManager` is the snapshot variable store (name validation, type classification, unparsable values kept as invalid NaN rows). Zero Qt dependency.
- **ViewModel** (`python/viewmodel/`) — Qt bridge layer. `QObject` subclasses expose properties, signals and slots to QML. `VariablesModel` (table) and `HistoryModel` (list) feed the table / card views with granular signals. Theme-aware LaTeX rendering lives in `python/latex_render.py` (ziamath), keyboard layout in `python/keyboard_config.py` (YAML).
- **View** (`qml/`) — Qt Quick UI only: a `FluentWindow` with RinUI's `NavigationView`, five pages, and the shared components (`KeyboardPanel`, `HScrollView`, `LatexImage`, focus-aware `SegmentedItem`/`SelectorBarItem`). No business logic.
- **Composition root** (`main.py`) — Builds `MainViewModel`, registers the viewmodels as flat QML context properties (`vm`, `calcVM`, `varsVM`, `historyVM`, `logVM`, `variablesModel`, `keyboardTabs`), and starts the QML engine via RinUI's `RinUIWindow`.

A request flows: **QML event → ViewModel slot → Model → SymPy → result → LaTeX/SVG → QML**. A detailed walkthrough lives in [`docs/architecture.md`](docs/architecture.md).

## Project Structure

```
main.py                        # Entry point (composition root)
python/
  model/                       # Pure business logic, zero Qt
    calculator.py              #   Calculator (evaluate / assign), Assignment,
                               #   Success / Failure, ErrorKind, render_latex
    variable.py                #   VariableManager (snapshot entries), name rules,
                               #   sympy name table, classify_type
  viewmodel/                   # Qt bridge (QObject + models)
    input_mode.py              #   InputMode (UI state: CODE / ASSIGN)
    main_viewmodel.py          #   Root VM, aggregates all children
    calculator_viewmodel.py    #   Result state, LaTeX SVG, calculate slots
    variables_viewmodel.py     #   VariablesModel (3-column) + CRUD
    history_viewmodel.py       #   HistoryModel (card list, lazy LaTeX)
    search.py                  #   Search filters for the Variables/History pages
    settings_viewmodel.py      #   Settings: appearance, rendering, window, config path
    log_viewmodel.py           #   LogViewModel
  settings.py                  # Settings store: config location, YAML, validation
  rinui_bootstrap.py           # Takes RinUI's own config directory over (see the guide)
  latex_render.py              # LaTeX -> SVG via ziamath (theme-colored, sized)
  keyboard_config.py           # Keyboard layout from keyboard_config.yaml
qml/
  MainWindow.qml               # FluentWindow + RinUI navigation
  components/                  # KeyboardPanel, HScrollView, LatexImage, SearchBar,
                               # SegmentedItem, SelectorBarItem, qmldir
  pages/                       # Calculator, Variables, History, Log, Settings
tests/
  test_model.py                # Behaviour contract of the model + viewmodels
  test_settings.py             # Settings store, config paths, RinUI bootstrap
  __main__.py                  # uv run python -m tests  (runs every module)
docs/
  architecture.svg             # Architecture diagram (model-focused)
  architecture.md              # Architecture walkthrough
test_plot.py                   # Experimental SymPy->GLSL GPU prototype (kept
                               # as a seed for the future plotting track)
```

## Usage

### Code Mode

Type any valid SymPy expression and press **Ctrl+Return** (or click **Calculate**):

| Expression | Result |
|---|---|
| `diff(x**2, x)` | $2x$ |
| `integrate(sin(x), x)` | $-\cos(x)$ |
| `limit(sin(x)/x, x, 0)` | $1$ |
| `solve(x**2 - 4, x)` | $[-2, 2]$ |
| `Matrix([[1,2],[3,4]]).det()` | $-2$ |

Use the **Examples** dropdown to fill and run a sample expression.

### Assign Mode

Switch to Assign mode via the segmented control. A three-part input appears:

```text
[ variable name ]  [ ▼ = ]  [ expression ]
```

Type your variable name, then press `=` to jump to the value field. The operator dropdown also supports `+=`, `-=`, `*=`, `/=` for augmented assignments. Press **Ctrl+Return** to assign. Assigning to a SymPy built-in constant (like `pi` or `E`) triggers a friendly warning.

### Variables

Use the Variables page (left navigation) to view, add, delete, rename, or double-click-edit variables. Each row shows the name, the expression, and a coarse type (`Integer`, `Expression`, `Matrix`, ...). Variables reference each other as sympy snapshots; an invalid assignment is kept in the list with a `NaN` value so the input is never lost. The search box filters the rows live (fuzzy / name / value / type); adding a variable clears the query so the new row is visible.

### History

Every calculation becomes a card (newest first) showing the input, the aligned result, and the rendered $\LaTeX$. Hover or focus a card to reveal its *Send to input* button (also in the context menu) — it jumps back to the calculator with the expression restored in Code or Assign mode. Right-click (or press `Shift+F10`) for Copy value/result, Copy $\LaTeX$, and Send to input. A calculation that fails becomes a card as well — showing the failure reason in red instead of a result — and *Send to input* restores the offending expression so it can be fixed. The search box filters the cards live (fuzzy / expression / result); the *expression* mode matches the input line as the card shows it, so an assignment is found by its whole `name = value` statement, and the *result* mode matches failures by their message too.

### Keyboard Panel

Click the on-screen keyboard to insert functions, Greek letters, operators and digits. The layout is defined in `python/keyboard_config.yaml`.

### Settings

Theme mode, backdrop effect (Windows 11), accent colour, result font size and whether the window geometry is remembered. Everything is written immediately to a single YAML file, and the *Settings file* row shows where that is — click it to open the folder.

The location is chosen at launch:

1. **Portable** — if a `Data` folder sits next to the app (`symplify.exe`, or the repository root when running from source), the file is `Data/config.yaml` and nothing outside that folder is touched. Delete or move the folder to go back to the system location.
2. **System** — otherwise the OS convention: `%APPDATA%\Symplify\config.yaml` (Windows), `$XDG_CONFIG_HOME/symplify/config.yaml` (Linux), `~/Library/Application Support/Symplify/config.yaml` (macOS).

The file is meant to be hand-editable (comments and unknown keys survive, invalid values fall back to their defaults), and a location that cannot be written is not fatal — the app keeps running with the values applied in memory and says so on the settings page. RinUI's own `RinUI/config` folder is never created: its theme/backdrop/accent settings live in this file instead.

## Dependencies

| Package | Purpose | License |
|---|---|---|
| [PySide6](https://doc.qt.io/qtforpython-6/) | Qt 6 for Python (QML runtime, Qt Quick Controls) | LGPLv3 |
| [RinUI](https://github.com/RinLit-233-shiroko/Rin-UI) | Fluent Design-like QML component library | MIT |
| [SymPy](https://sympy.org) | Symbolic mathematics engine | BSD |
| [ziamath](https://github.com/vvandijck/ziamath) | LaTeX to SVG math rendering | MIT |
| [PyYAML](https://pyyaml.org) | Keyboard layout config | MIT |

## Roadmap

Prioritized directions:

1. **Persistence & settings** — *done for settings* (theme, accent colour, backdrop, $\LaTeX$ size, window geometry, portable or system location); variables and history are still in-memory and are the next candidates for the same store.
2. **Variables refresh** — a preview panel (numeric approximation + large $\LaTeX$); search/filter is done.
3. **History search & export** — *search done*; save/export recorded calculations is open.
4. **Settings polish** — *done*; further options (fonts, key bindings) fit the same store.
5. **Plotting** — classic 2D plotting first (via SymPy), then a Desmos-grade GPU plotting pipeline; plus optional SymPy convenience UIs (physics, geometry, code generation).

## License

Symplify is licensed under [GPLv3](LICENSE).
