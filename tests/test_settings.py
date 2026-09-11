# coding: utf-8
"""Behaviour tests for the settings store and the RinUI bootstrap.

Run from the repository root:

    uv run python -m tests.test_settings     # this module alone
    uv run python -m tests                   # every test module

Plain asserts plus a runner, no test framework needed. Everything runs against
temporary directories with an injected environment, so the real user config
directory is never touched.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.settings import (  # noqa: E402
    CONFIG_FILENAME,
    DEFAULTS,
    SettingsStore,
    resolve_config_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="symplify_test_"))


# --------------------------------------------------------------------------
# Where the config lives
# --------------------------------------------------------------------------

def test_portable_data_dir_wins_over_everything():
    root = temp_dir()
    (root / "Data").mkdir()
    directory, portable = resolve_config_dir(
        root, {"APPDATA": "C:/Roaming", "XDG_CONFIG_HOME": "/x"}
    )
    assert portable is True
    assert directory == root / "Data"


def test_windows_config_dir():
    root = temp_dir()
    home = {"HOME": "C:/Users/me"}
    assert resolve_config_dir(root, {**home, "APPDATA": "C:/Roaming"}, "windows")[0] == \
        Path("C:/Roaming/Symplify")
    assert resolve_config_dir(root, {**home, "LOCALAPPDATA": "C:/Local"}, "windows")[0] == \
        Path("C:/Local/Symplify")
    assert resolve_config_dir(root, home, "windows")[0] == Path("C:/Users/me/Symplify")
    assert resolve_config_dir(root, home, "windows")[1] is False


def test_linux_config_dir_follows_xdg():
    root = temp_dir()
    assert resolve_config_dir(
        root, {"XDG_CONFIG_HOME": "/home/me/.config"}, "linux"
    )[0] == Path("/home/me/.config/symplify")
    assert resolve_config_dir(root, {"HOME": "/home/me"}, "linux")[0] == \
        Path("/home/me/.config/symplify")


def test_macos_config_dir():
    root = temp_dir()
    assert resolve_config_dir(root, {"HOME": "/Users/me"}, "macos")[0] == \
        Path("/Users/me/Library/Application Support/Symplify")


# --------------------------------------------------------------------------
# The store
# --------------------------------------------------------------------------

def store_at(path: Path) -> SettingsStore:
    store = SettingsStore(path)
    store.load()
    return store


def test_missing_file_yields_defaults_without_creating_it():
    path = temp_dir() / CONFIG_FILENAME
    store = store_at(path)
    assert store.get("appearance.theme") == DEFAULTS["appearance"]["theme"]
    assert store.warning == ""
    # Reading must never write: an unwritable install stays usable until the
    # user actually changes something.
    assert not path.exists()


def test_set_persists_and_round_trips():
    path = temp_dir() / CONFIG_FILENAME
    store = store_at(path)
    assert store.set("appearance.theme", "Dark") == "Dark"
    assert path.is_file()
    assert store_at(path).get("appearance.theme") == "Dark"


def test_unknown_keys_survive_a_write():
    path = temp_dir() / CONFIG_FILENAME
    path.write_text(
        "version: 1\nappearance:\n  theme: Light\nmy_own_key:\n  keep: 7\n",
        encoding="utf-8",
    )
    store = store_at(path)
    assert store.get("appearance.theme") == "Light"
    store.set("rendering.latex_size", 20)
    reloaded = store_at(path)
    assert reloaded.values["my_own_key"] == {"keep": 7}
    assert reloaded.get("appearance.theme") == "Light"
    assert reloaded.get("rendering.latex_size") == 20


def test_invalid_values_fall_back_to_defaults():
    path = temp_dir() / CONFIG_FILENAME
    path.write_text(
        "appearance:\n  theme: Purple\n  backdrop: 5\n  accent: red\n"
        "rendering:\n  latex_size: abc\nwindow:\n  x: nowhere\n",
        encoding="utf-8",
    )
    store = store_at(path)
    assert store.get("appearance.theme") == "Auto"
    assert store.get("appearance.backdrop") == "mica"
    assert store.get("appearance.accent") == DEFAULTS["appearance"]["accent"]
    assert store.get("rendering.latex_size") == 24
    assert store.get("window.x") is None


def test_numeric_values_are_clamped():
    path = temp_dir() / CONFIG_FILENAME
    store = store_at(path)
    assert store.set("rendering.latex_size", 999) == 96
    assert store.set("rendering.latex_size", 3) == 8
    assert store.set("window.width", 10) == 860
    assert store.set("window.height", 999999) == 20000


def test_window_coordinates_and_flags():
    path = temp_dir() / CONFIG_FILENAME
    store = store_at(path)
    assert store.set("window.x", 120) == 120
    assert store.set("window.x", "abc") is None
    assert store.set("window.maximized", 1) is True
    assert store.set("window.remember", 0) is False


def test_corrupt_yaml_never_breaks_startup():
    path = temp_dir() / CONFIG_FILENAME
    path.write_text("{{{{ not yaml", encoding="utf-8")
    store = store_at(path)
    assert store.get("appearance.theme") == "Auto"
    assert "unreadable" in store.warning


def test_non_mapping_yaml_falls_back_to_defaults():
    path = temp_dir() / CONFIG_FILENAME
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    store = store_at(path)
    assert store.values["appearance"]["theme"] == "Auto"


def test_writes_are_atomic_and_leave_no_temp_file():
    path = temp_dir() / CONFIG_FILENAME
    store = store_at(path)
    store.set("appearance.theme", "Light")
    assert store.save() is True
    leftovers = [p.name for p in path.parent.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_unwritable_target_keeps_values_in_memory_and_warns():
    blocker = temp_dir() / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    store = store_at(blocker / CONFIG_FILENAME)
    assert store.set("appearance.theme", "Dark") == "Dark"   # still applied
    assert store.get("appearance.theme") == "Dark"
    assert store.warning != ""


def test_reset_restores_every_default():
    path = temp_dir() / CONFIG_FILENAME
    store = store_at(path)
    store.set("appearance.theme", "Dark")
    store.set("rendering.latex_size", 40)
    store.reset()
    assert store.values == DEFAULTS
    assert store_at(path).get("appearance.theme") == "Auto"


def test_portable_store_writes_into_the_data_dir():
    root = temp_dir()
    (root / "Data").mkdir()
    store = SettingsStore.open(root, {}, "windows")
    assert store.is_portable is True
    store.set("appearance.theme", "Dark")
    assert (root / "Data" / CONFIG_FILENAME).is_file()


def test_open_prefers_the_system_dir_without_a_data_dir():
    root = temp_dir()
    appdata = temp_dir()
    store = SettingsStore.open(root, {"APPDATA": str(appdata)}, "windows")
    assert store.is_portable is False
    assert store.path == appdata / "Symplify" / CONFIG_FILENAME


# --------------------------------------------------------------------------
# The window's startup size (read by MainWindow.qml at creation)
# --------------------------------------------------------------------------

def test_startup_size_follows_the_remembered_geometry():
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"window.remember": True, "window.width": 1024, "window.height": 620})
    vm = SettingsViewModel(store)
    assert (vm.startupWidth, vm.startupHeight) == (1024, 620)


def test_startup_size_ignores_a_remembered_geometry_when_not_remembering():
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"window.remember": False, "window.width": 1024, "window.height": 620})
    vm = SettingsViewModel(store)
    assert vm.startupWidth == DEFAULTS["window"]["width"]
    assert vm.startupHeight == DEFAULTS["window"]["height"]


# --------------------------------------------------------------------------
# The RinUI bootstrap (needs a fresh process: RinUI's config is built on import)
# --------------------------------------------------------------------------

BOOT_SCRIPT = r"""
import json, os, sys
from pathlib import Path

root = Path(sys.argv[1])
from python.rinui_bootstrap import prepare

runtime = prepare(root)
settings, RinUIWindow = runtime.settings, runtime.window_class

from RinUI.core.config import RinConfig
print("STORE", settings.path)
print("THEME", settings.get("appearance.theme"))
print("BACKDROP", settings.get("appearance.backdrop"))
print("ACCENT", settings.get("appearance.accent"))
print("RINUI", json.dumps(RinConfig.config, sort_keys=True))
RinConfig["theme"] = {"current_theme": "Light"}       # must not touch disk
RinConfig.upload_config("theme_color", "#000000")
print("ROOT_ENTRIES", sorted(p.name for p in root.iterdir()))
placeholder = settings.path.parent / "RinUI" / "config" / "rin_ui.json"
print("PLACEHOLDER", placeholder.read_text(encoding="utf-8").strip())
print("WINDOW", RinUIWindow.__name__)
print("VERSION", runtime.rinui_version)
"""


def run_bootstrap(root: Path, appdata: Path) -> dict:
    """Run the bootstrap in a fresh interpreter and parse its report."""
    result = subprocess.run(
        [sys.executable, "-c", BOOT_SCRIPT, str(root)],
        cwd=str(REPO_ROOT),
        env={**os.environ, "APPDATA": str(appdata), "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    report = {}
    for line in result.stdout.splitlines():
        if " " in line and line.split(" ", 1)[0].isupper():
            key, value = line.split(" ", 1)
            report[key] = value
    return report


def test_bootstrap_migrates_removes_and_never_writes_again():
    root = temp_dir()
    appdata = temp_dir()
    (root / "qml").mkdir()                      # unrelated content must survive
    legacy = root / "RinUI" / "config"
    legacy.mkdir(parents=True)
    (legacy / "rin_ui.json").write_text(json.dumps({
        "theme": {"current_theme": "Dark"},
        "theme_color": "#ff8800",
        "backdrop_effect": "acrylic",
    }), encoding="utf-8")

    report = run_bootstrap(root, appdata)

    # the legacy directory is gone, the app root is otherwise untouched
    assert report["ROOT_ENTRIES"] == "['qml']"
    assert not (root / "RinUI").exists()
    # its values were folded into our settings file
    assert report["THEME"] == "Dark"
    assert report["BACKDROP"] == "acrylic"
    assert report["ACCENT"] == "#ff8800"
    assert str(appdata) in report["STORE"]
    # RinUI runs on our values but can no longer persist anything
    assert '"current_theme": "Dark"' in report["RINUI"]
    assert '"backdrop_effect": "acrylic"' in report["RINUI"]
    assert report["PLACEHOLDER"] == "{}"
    assert report["WINDOW"] == "RinUIWindow"
    assert report["VERSION"].count(".") >= 1


def test_bootstrap_leaves_the_launch_dir_clean_without_a_legacy_config():
    root = temp_dir()
    appdata = temp_dir()
    report = run_bootstrap(root, appdata)
    assert report["ROOT_ENTRIES"] == "[]"
    assert report["PLACEHOLDER"] == "{}"
    assert report["THEME"] == "Auto"


def test_bootstrap_second_run_keeps_the_users_own_settings():
    """A legacy file on a *later* run must not clobber the settings file."""
    root = temp_dir()
    appdata = temp_dir()
    run_bootstrap(root, appdata)

    store = SettingsStore.open(root, {"APPDATA": str(appdata)}, "windows")
    store.set("appearance.theme", "Light")

    report = run_bootstrap(root, appdata)
    assert report["THEME"] == "Light"


def main() -> int:
    """Run every test_* function in this module."""
    tests = sorted(
        (name, obj)
        for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    )
    failures = []
    for name, fn in tests:
        try:
            fn()
        except Exception as exc:
            failures.append(name)
            print(f"FAIL  {name}\n      {type(exc).__name__}: {exc}")
        else:
            print(f"PASS  {name}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
