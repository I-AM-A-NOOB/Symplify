<p align="center">
  <h1 align="center">Symplify</h1>
  <p align="center">A modern symbolic calculator built with SymPy and PySide6/QML.</p>
</p>

Symplify puts SymPy behind a Fluent desktop UI. The interface is QML (RinUI); the
calculation core is pure Python with no Qt dependency, and the ViewModels are the
only Qt bridge. The current line is **0.7.x**: the calculator, variables, history,
themes and 2-D plotting are usable; plotting is still a preview.

Latest release: **[v0.7.2](https://github.com/I-AM-A-NOOB/Symplify/releases/latest)**

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
- **On-screen keyboard** — seven YAML-configured tabs, with mathematical glyphs
  that insert plain SymPy syntax.
- **Themes and typography** — light/dark/system themes follow the OS live, three
  configurable font stacks and a single hand-editable YAML settings file.
- **Focus navigation** — `Ctrl+Tab` / `Ctrl+Shift+Tab` cycle focus;
  `Ctrl+Return` calculates.

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
