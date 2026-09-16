# coding: utf-8
"""Build Symplify for Windows with Nuitka (MSVC, standalone dir, optimized).

Produces ``build/main.dist/symplify.exe`` plus the QML/RinUI resources, then
prunes the Qt modules the app never loads — Nuitka's PySide6 plugin bundles
*every* Qt module otherwise (QtWebEngineCore alone is 205 MB of the 513 MB dist).

Run from the repository root::

    uv run python scripts/build_windows.py                # build + prune
    uv run python scripts/build_windows.py --prune-only   # re-prune an existing dist
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "build" / "main.dist"

#: Name of the config file RinUI writes into its own directory (see below).
_RINUI_FILENAME = "rin_ui.json"

CMD = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--assume-yes-for-downloads",
    "--output-dir=build",
    "--output-filename=symplify",
    "--enable-plugin=pyside6",
    "--include-qt-plugins=qml",
    "--msvc=latest",
    # LTO off on purpose: the /GL + /LTCG link is single-threaded and is a large
    # slice of the build time, for no measurable runtime gain in a calculator.
    "--lto=no",
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
    # fontTools reads installed fonts (python/fonts.py: which ones can typeset
    # maths). Imported lazily inside functions, so make it explicit.
    "--include-package=fontTools",
    # our package data (keyboard_config.yaml lives next to the module)
    "--include-package-data=python",
    # QML views (loaded by path at runtime next to the exe)
    "--include-data-dir=qml=qml",
    "main.py",
]

# ---------------------------------------------------------------------------
# Pruning the Qt modules the app never loads
# ---------------------------------------------------------------------------
# The lists below are not guesses. Both come from the running build, and each
# entry is justified by evidence:
#
# * KEEP_QT_DLLS is exactly what a started ``main.dist/symplify.exe`` has mapped
#   (``(Get-Process symplify).Modules``). Note the non-obvious entries: Qt6Pdf
#   and Qt6ShaderTools *are* loaded (the Qt Quick Controls stack pulls them in),
#   and Qt6QuickControls2Fusion + ...WindowsStyleImpl are loaded alongside the
#   Basic style the pages import explicitly.
# * PRUNE_QML_DIRS holds QML modules nothing reaches. Verified by walking the
#   ``import`` closure from the app's and RinUI's own QML: e.g. QtMultimedia and
#   Qt.labs.folderlistmodel are imported *only* from QtQuick/VirtualKeyboard and
#   QtQuick/Dialogs, which nothing imports in turn. QtQuick/NativeStyle is
#   deliberately absent from this list — the Windows style (38 files under
#   QtQuick/Controls/Windows) imports it.
#
# Keep both in step with the Qt version: a bump can add or rename DLLs, and a
# name that is missing from KEEP_QT_DLLS is deleted.

#: Qt DLLs the app actually loads. Lowercase; everything else ``qt6*.dll`` goes.
KEEP_QT_DLLS = frozenset({
    "qt6core.dll",
    "qt6gui.dll",
    "qt6network.dll",
    "qt6opengl.dll",
    "qt6pdf.dll",
    "qt6qml.dll",
    "qt6qmlmeta.dll",
    "qt6qmlmodels.dll",
    "qt6qmlworkerscript.dll",
    "qt6quick.dll",
    "qt6quickcontrols2.dll",
    "qt6quickcontrols2basic.dll",
    "qt6quickcontrols2basicstyleimpl.dll",
    "qt6quickcontrols2fusion.dll",
    "qt6quickcontrols2impl.dll",
    "qt6quickcontrols2windowsstyleimpl.dll",
    "qt6quickeffects.dll",
    "qt6quicklayouts.dll",
    "qt6quickshapes.dll",
    "qt6quicktemplates2.dll",
    "qt6shadertools.dll",
    "qt6svg.dll",
    "qt6widgets.dll",
})

#: QML module directories under ``PySide6/qml`` the app never reaches.
PRUNE_QML_DIRS = (
    # whole modules nothing imports
    "Qt3D",
    "QtCharts",
    "QtDataVisualization",
    "QtGraphs",
    "QtLocation",
    "QtMultimedia",
    "QtPositioning",
    "QtQuick3D",
    "QtRemoteObjects",
    "QtScxml",
    "QtSensors",
    "QtTest",
    "QtTextToSpeech",
    "QtWebChannel",
    "QtWebEngine",
    "QtWebSockets",
    "QtWebView",
    "Qt",                                # only Qt.labs.*, reached from the dirs below
    # QtQuick submodules nothing imports
    "QtQuick/Dialogs",
    "QtQuick/VirtualKeyboard",
    "QtQuick/LocalStorage",
    "QtQuick/Particles",
    "QtQuick/Timeline",
    "QtQuick/VectorImage",
    "QtQuick/Scene2D",
    "QtQuick/Scene3D",
    "QtQuick/tooling",
    # Nothing imports QtQuick.Pdf; its +Material/+Universal style variants are
    # what still referenced the two style dirs pruned above. (qt6pdf.dll itself
    # *is* loaded by the Qt Quick Controls stack, so the DLL stays.)
    "QtQuick/Pdf",
    # Controls styles other than the ones in use (Basic, plus the Fusion base of
    # the Windows style); the running app loads neither of these style plugins
    "QtQuick/Controls/FluentWinUI3",
    "QtQuick/Controls/Imagine",
    "QtQuick/Controls/Material",
    "QtQuick/Controls/Universal",
    "QtQuick/Controls/designer",
)


def _size(path: Path) -> int:
    """Bytes under ``path`` (a file or a directory tree)."""
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def prune_qt(dist: Path) -> int:
    """Delete the unused Qt modules from ``dist``; return the bytes freed."""
    freed = 0

    for dll in sorted(dist.glob("qt6*.dll")):
        if dll.name.lower() not in KEEP_QT_DLLS:
            freed += _size(dll)
            dll.unlink()

    qml_root = dist / "PySide6" / "qml"
    for relative in PRUNE_QML_DIRS:
        target = qml_root / relative
        if target.exists():
            freed += _size(target)
            shutil.rmtree(target)

    return freed


def cleanup_rinui_dir() -> None:
    """Remove the config directory RinUI drops in the project root.

    ``python/rinui_bootstrap.py`` keeps that directory away at *runtime*, but
    Nuitka imports RinUI while analysing the program, and that import happens
    outside the bootstrap — so a build leaves ``<root>/RinUI/config/rin_ui.json``
    behind. Only its own config file is deleted and the folders are dropped with
    ``rmdir``, so anything else in there survives.
    """
    config = ROOT / "RinUI" / "config" / _RINUI_FILENAME
    if not config.is_file():
        return
    config.unlink()
    for folder in (config.parent, config.parent.parent):
        try:
            folder.rmdir()
        except OSError:
            pass          # not empty: leave whatever else is in there


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prune-only", action="store_true",
                        help="re-prune an existing build/main.dist (no Nuitka run)")
    args = parser.parse_args()

    if args.prune_only:
        if not DIST.is_dir():
            sys.exit(f"no dist to prune at {DIST}")
        print(f"Pruned {prune_qt(DIST) / 1e6:.1f} MB from {DIST}")
        return 0

    print("Nuitka build root:", ROOT)
    code = subprocess.call(CMD, cwd=ROOT)
    cleanup_rinui_dir()
    if code == 0:
        print(f"Pruned {prune_qt(DIST) / 1e6:.1f} MB of unused Qt modules")
    return code


if __name__ == "__main__":
    sys.exit(main())
