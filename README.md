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
- **History Cards** — Newest-first cards with rendered $\LaTeX$, timestamps, a context menu (copy value/result, copy $\LaTeX$), and *Send to input* to restore any entry in the calculator.
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

## Architecture

Symplify follows **MVVM**. The `python/` package is split into layers; the model is pure Python with no Qt imports, which keeps it unit-testable and independent of any UI framework.

![Architecture diagram, model-focused](docs/architecture.svg)

- **Model** (`python/model/`) — Pure business logic: `Calculator` (SymPy evaluation), `VariableManager` (snapshot variable store with validation and type classification), `InputMode` / `ResultType` enums, and the `CalculationResult` dataclass. Zero Qt dependency.
- **ViewModel** (`python/viewmodel/`) — Qt bridge layer. `QObject` subclasses expose properties, signals and slots to QML. `VariablesModel` (table) and `HistoryModel` (list) feed the table / card views with granular signals. Theme-aware LaTeX rendering lives in `python/latex_render.py` (ziamath), keyboard layout in `python/keyboard_config.py` (YAML).
- **View** (`qml/`) — Qt Quick UI only: a `FluentWindow` with RinUI's `NavigationView`, five pages, and the shared components (`KeyboardPanel`, `HScrollView`, `LatexImage`, focus-aware `SegmentedItem`/`SelectorBarItem`). No business logic.
- **Composition root** (`main.py`) — Builds `MainViewModel`, registers the viewmodels as flat QML context properties (`vm`, `calcVM`, `varsVM`, `historyVM`, `logVM`, `variablesModel`, `keyboardTabs`), and starts the QML engine via RinUI's `RinUIWindow`.

A request flows: **QML event → ViewModel slot → Model → SymPy → result → LaTeX/SVG → QML**. A detailed walkthrough lives in [`docs/architecture.md`](docs/architecture.md).

## Project Structure

```
main.py                        # Entry point (composition root)
python/
  model/                       # Pure business logic, zero Qt
    calculator.py              #   Calculator, CalculationResult, ResultType
    variable.py                #   VariableManager (snapshot entries) + classify_type
    input_mode.py              #   InputMode (CODE / ASSIGN)
  viewmodel/                   # Qt bridge (QObject + models)
    main_viewmodel.py          #   Root VM, aggregates all children
    calculator_viewmodel.py    #   Result state, LaTeX SVG, calculate slots
    variables_viewmodel.py     #   VariablesModel (3-column) + CRUD
    history_viewmodel.py       #   HistoryModel (card list, lazy LaTeX)
    log_viewmodel.py           #   LogViewModel
  latex_render.py              # LaTeX -> SVG via ziamath (theme-colored)
  keyboard_config.py           # Keyboard layout from keyboard_config.yaml
qml/
  MainWindow.qml               # FluentWindow + RinUI navigation
  components/                  # KeyboardPanel, HScrollView, LatexImage,
                               # SegmentedItem, SelectorBarItem, qmldir
  pages/                       # Calculator, Variables, History, Log, Settings
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

Use the Variables page (left navigation) to view, add, delete, rename, or double-click-edit variables. Each row shows the name, the expression, and a coarse type (`Integer`, `Expression`, `Matrix`, ...). Variables reference each other as sympy snapshots; an invalid assignment is kept in the list with a `NaN` value so the input is never lost.

### History

Every calculation becomes a card (newest first) showing the input, the aligned result, and the rendered $\LaTeX$. Hover or focus a card to reveal its *Send to input* button (also in the context menu) — it jumps back to the calculator with the expression restored in Code or Assign mode. Right-click (or press `Shift+F10`) for Copy value/result, Copy $\LaTeX$, and Send to input.

### Keyboard Panel

Click the on-screen keyboard to insert functions, Greek letters, operators and digits. The layout is defined in `python/keyboard_config.yaml`.

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

1. **Persistence & settings** — a pure-Python store for user settings (theme, accent color, $\LaTeX$ size), variables and history; the settings page reads from it.
2. **Variables refresh** — search/filter and a preview panel (numeric approximation + large $\LaTeX$).
3. **History search & export** — filter the card list; save/export recorded calculations.
4. **Settings polish** — fonts, theme color, backdrop, all persisted.
5. **Plotting** — classic 2D plotting first (via SymPy), then a Desmos-grade GPU plotting pipeline; plus optional SymPy convenience UIs (physics, geometry, code generation).

## License

Symplify is licensed under [GPLv3](LICENSE).
