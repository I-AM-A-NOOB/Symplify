<p align="center">
  <h1 align="center">Symplify</h1>
  <p align="center"><b>A modern symbolic calculator that puts SymPy behind a Fluent desktop UI.</b></p>
</p>
<p style="text-align: center;">made by I-AM-A-NOOB using <img
  src="/docs/assets/token.jpg"
  alt="DeepSeek"
  style="height: 50px; width: auto; vertical-align: middle; display: inline-block;"></p>

## Features

- **Symbolic & numeric computation** — derivatives, integrals, limits, equation
  solving and matrices via SymPy, shown as plain text and rendered LaTeX.
- **Alternative forms** — a result card below the formula offers the forms worth
  seeing: evaluated (`doit`), numeric (`N`), expanded and factored.
- **Responsive calculations** — evaluation runs in a spawned backend process with
  a 10-second deadline, so a hard expression cannot freeze the window; the
  result header reports ready / busy / timed out / failed.
- **Plotting preview** — results in `x` (or `x` and `y`) are drawn with
  qmlmathplot; `diff`/`integrate` show the source and the result, `solve` shows
  the equation it solved. Unsupported or unevaluated forms are skipped.
- **Code and Assign modes** — evaluate expressions, or write variables with
  `=`, `+=`, `-=`, `*=`, `/=`; the mode and inputs survive page switches.
- **Variables and history** — snapshot variables with inline editing and search;
  every calculation becomes a searchable history card with copy and *Send to
  input*.
- **On-screen keyboard** — seven YAML-configured tabs plus user copies in the
  settings folder, an uppercase Shift layer, cursor keys and selection-aware
  Backspace; mathematical glyphs are typeset through the LaTeX renderer and
  insert plain SymPy syntax.
- **Themes and typography** — light/dark/system themes follow the OS live, three
  configurable font stacks and a single hand-editable YAML settings file.
- **Focus navigation** — `Ctrl+Tab` / `Ctrl+Shift+Tab` cycle focus;
  `Ctrl+Return` calculates.

## Roadmap

Planned UI work and new features, in dependency order. This is a roadmap, not a
release schedule.

### Calculator workspace

The main page does **not** need a full-page UI refresh or another outer scroll
container. It needs clearer responsibilities between the input, results and plot.

- **P0 — separate the plot from the result scroller.** Move the plot out of
  `resultScroll` and make the right column a vertical `SplitView`: a scrollable
  result area above, a fixed/resizable plot below. This removes the scrollbar
  versus plot-wheel conflict and lets a long formula scroll without dragging the
  plot away.
- **P1 — make the left column elastic.** Let the input grow or be dragged up to a
  cap, scroll internally past it, make the on-screen keyboard collapsible, and add
  a lightweight **Focus result** toggle that collapses the input pane.
- **P2 — small-window fallback.** When height is short, turn the right column into
  `Result` / `Plot` tabs instead of squeezing both.
- **P3 — remember layout state.** Persist splitter ratios, keyboard collapsed
  state and Focus result across sessions.

### Editor and language

- **VSCode-style input / IntelliSense.** Autocomplete for variables, functions and
  constants; signature help; inline diagnostics; bracket matching. This needs a
  stable expression language and a completion service over the existing backend
  boundary; the Variables page's synchronous inline edit is a prerequisite to
  move through the same path.
- **Parser switches in Settings.** Expose a small set of named semantic choices
  (for example `^` as power vs XOR, implicit multiplication) rather than raw
  `parse_expr` kwargs. The lexer, highlighting, bracket pairing and diagnostics
  must follow the same rules, with migration notes for stored expressions.

### AI assistance

- **Formula authoring.** Turn a natural-language request into an expression,
  with a preview before it is inserted into the current Code/Assign input.
- **Explain and translate errors.** Explain parser/model failures in plain
  language and localize that explanation; the same flow can translate an
  unfamiliar error without changing the original failure record.
- **Boundary.** AI output is text until it goes through the normal safe parser
  and calculation worker; the model never gets an execution path of its own.

### Keyboard

- **Generalized and generated keyboard layers.** Custom keyboard YAML is shipped;
  the remaining work is to generalize per-tab labels/shift behavior and add a
  generated Greek layer without turning individual pages into special cases.

### Localization

- **Foundation in place.** The Language group is first in Settings, supports
  System default, and discovers compiled `i18n/symplify_<code>.qm` catalogues.
  `i18n/symplify.ts` is the Linguist template; `scripts/update_translations.py`
  runs `pyside6-lupdate`/`pyside6-lrelease`. Chinese catalogues use script
  codes (`zh_Hans` / `zh_Hant`); system locales map `zh_CN`/`zh_SG` to
  Simplified and `zh_TW`/`zh_HK`/`zh_MO` to Traditional, never across scripts.
  An optional `symplify_en.ts` can centrally override English copy while the
  QML `qsTr` source remains the fallback.
- **Next.** Translate the QML catalogue with Qt Linguist, then route Python-side
  user-facing strings through `tr()` as well. No runtime `.ts` compiler or
  translation cache is planned.

### Plot and presentation

- **Plot appearance choices.** Deferred until the workspace split is in place:
  selectable plot themes.
- **Icon and branding refresh.** The application icon still needs a proper design
  pass; the installer temporarily uses its default icon until then.

The detailed source architecture and invariants are in the
[architecture walkthrough](docs/architecture.md) and the
[developer guide](.Agent/DEVELOPER_GUIDE.md).

## Download

| Download | Notes |
|---|---|
| `Symplify-v<version>-windows-x64-portable.zip` | Extract and run `Symplify\symplify.exe`. The empty `data\` folder makes it portable: settings live in `data\config.yaml`, nothing outside the folder is touched. |
| `Symplify-v<version>-windows-x64-setup.exe` | Inno Setup installer: per-user by default, optional all-users, Start Menu/desktop shortcuts, and a clean uninstaller that removes the install directory and Qt's local cache. An installed copy keeps its settings in `%APPDATA%\Symplify\config.yaml`; the uninstaller asks before deleting them. Running a newer setup replaces an existing install cleanly. |

The portable zip is the only download that writes settings next to the app. The
installer never creates `data\`, so it always uses the OS config location.

## Run from source

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/I-AM-A-NOOB/Symplify.git
cd Symplify
uv sync
uv run python main.py
```

## Build and release

Windows standalone builds use Nuitka + MSVC; the installer needs
[Inno Setup 7](https://jrsoftware.org/isdl.php). Releases are built on a local
Windows machine (the CI runner cannot complete this build) and published with:

```bash
uv run python scripts/build_windows.py      # -> build/main.dist/symplify.exe
uv run python scripts/release.py minor      # bump version (SemVer)
uv run python scripts/release.py minor --publish   # bump, tag, build, package, publish
```

See the [developer guide](.Agent/DEVELOPER_GUIDE.md) for the full build, packaging,
versioning and architecture rules.

## Documentation

- [Architecture walkthrough](docs/architecture.md) — the model-first data flow and
  the backend boundary.
- [Developer guide](.Agent/DEVELOPER_GUIDE.md) — source layout, invariants, known
  Qt/RinUI traps, build and release details.
- [Command cheat sheet](scripts/cheat-sheet.md) — the day-to-day commands.

## License

Symplify is licensed under [GPLv3](LICENSE).

The accent-shade derivation in `python/accent.py` is the author's own
reconstruction of Windows' observed behaviour; its provenance and the "no
Microsoft source code or resources reproduced" note are documented in the
developer guide under *Settings & config → Accent*.
