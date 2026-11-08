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
- **Zen mode** — hides the input, most chrome and the navigation bar for
  result/plot reading. The title-bar button left of minimize enters and exits;
  `Ctrl+Alt+M` toggles it, and in windowed Zen a full-screen control sits beside
  it. In full screen, hovering the top strip (or tapping it) brings back the
  Exit Zen and normal minimize/windowed/close controls; a separate top InfoBar
  explains the exit keys. `Esc` leaves full screen first,
  then Zen — and also leaves a plain `F11` fullscreen — while `F11` toggles full
  screen. Whether entering Zen uses full screen is configurable.

## Roadmap

Planned UI work and new features, in dependency order. This is a roadmap, not a
release schedule.

### Calculator workspace

The page now has a page-level toolbar over a resizable **SplitView** (input |
result/plot). The plot is no longer inside the result scroller, and it moves
beside the result when the content area is wide enough. Result and plot default
to a 1:1 split and animate between horizontal and vertical arrangements. Result
copies live in the result pane header and plot reset/zoom in the plot pane
header, so neither toolbar covers the graph. The title-bar **Zen** control hides
the input, most of the toolbar and the navigation bar, and can optionally use
full screen with the window frame hidden (Settings → Workspace → *Full screen in
Zen mode*); a top-edge strip restores Exit Zen in full screen. `F11` toggles
full screen in any mode. The remaining work is:

- **P1 — finish the keyboard.** Its undo/redo sit beside the cursor keys; the
  on-screen keyboard still needs its own collapse control.
- **P2 — small-window fallback.** When height is short, turn the right area into
  `Result` / `Plot` tabs instead of squeezing both.
- **P3 — remember layout state.** Persist the outer splitter width, the
  result/plot ratio and the keyboard collapsed state across sessions.

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

- **Plot appearance choices.** With the result/plot split in place, selectable
  plot themes are the next presentation step.
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
