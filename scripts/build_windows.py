# coding: utf-8
"""Build Symplify for Windows with Nuitka (MSVC, standalone dir, optimized).

Produces ``build/main.dist/symplify.exe`` plus the QML/RinUI resources.
Run from the repository root:  uv run python scripts/build_windows.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CMD = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--assume-yes-for-downloads",
    "--output-dir=build",
    "--output-filename=symplify",
    "--enable-plugin=pyside6",
    "--msvc=latest",
    "--lto=yes",
    "--windows-console-mode=disable",
    # RinUI (python package + its QML module tree)
    "--include-package=RinUI",
    "--include-package-data=RinUI",
    # math font assets bundled in ziamath/ziafont (loaded via
    # importlib.resources, which Nuitka cannot discover by itself)
    "--include-module=ziamath.fonts",
    "--include-module=ziafont.fonts",
    "--include-package-data=ziamath",
    "--include-package-data=ziafont",
    # latex2mathml ships a symbol table that ziamath reads at runtime
    "--include-package-data=latex2mathml",
    # our package data (keyboard_config.yaml lives next to the module)
    "--include-package-data=python",
    # QML views (loaded by path at runtime next to the exe)
    "--include-data-dir=qml=qml",
    "main.py",
]


def main() -> int:
    print("Nuitka build root:", ROOT)
    return subprocess.call(CMD, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
