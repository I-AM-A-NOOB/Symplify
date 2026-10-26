"""Update Qt Linguist sources and compile every translated catalogue.

The source language is English. `i18n/symplify.ts` is the template translators
open in Qt Linguist; each `i18n/symplify_<code>.ts` is one target language. This
script deliberately uses the `pyside6-lupdate` / `pyside6-lrelease` tools that
ship with PySide6, so translators do not need a separate Qt installation.

Run from the repository root:

    uv run python scripts/update_translations.py

To add a language, copy the template to `i18n/symplify_<code>.ts`, translate it
in Qt Linguist, then run this script again. The app discovers the resulting
`.qm` files at startup; it never compiles `.ts` files at runtime.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "i18n"
TEMPLATE = I18N / "symplify.ts"


def _tool(name: str) -> str:
    """Find a PySide6 tool in the running interpreter's environment."""
    executable = Path(sys.executable).with_name(
        f"{name}.exe" if sys.platform == "win32" else name
    )
    if executable.is_file():
        return str(executable)
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(f"{name} was not found; install the PySide6 tools")


def _run(argv: list[str]) -> None:
    print(">", " ".join(argv))
    subprocess.run(argv, cwd=ROOT, check=True)


def main() -> int:
    I18N.mkdir(exist_ok=True)
    lupdate = _tool("pyside6-lupdate")
    lrelease = _tool("pyside6-lrelease")

    # The template is always regenerated from the QML sources. Locations are
    # relative to the .ts file, so Linguist can jump back into the tree.
    _run([lupdate, "qml", "-extensions", "qml", "-ts", str(TEMPLATE)])

    targets = sorted(path for path in I18N.glob("symplify_*.ts")
                     if path != TEMPLATE)
    if not targets:
        print("No translated .ts files yet; only the template was updated.")
        return 0

    for path in targets:
        _run([lupdate, "qml", "-extensions", "qml", "-ts", str(path)])
        _run([lrelease, str(path), "-qm", str(path.with_suffix(".qm"))])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
