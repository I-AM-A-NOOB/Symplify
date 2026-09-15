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

from PySide6.QtCore import QObject, Qt, Signal  # noqa: E402

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
    (root / "data").mkdir()
    directory, portable = resolve_config_dir(
        root, {"APPDATA": "C:/Roaming", "XDG_CONFIG_HOME": "/x"}
    )
    assert portable is True
    assert directory == root / "data"


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
    store.set("fonts.latex_size", 20)
    reloaded = store_at(path)
    assert reloaded.values["my_own_key"] == {"keep": 7}
    assert reloaded.get("appearance.theme") == "Light"
    assert reloaded.get("fonts.latex_size") == 20


def test_invalid_values_fall_back_to_defaults():
    path = temp_dir() / CONFIG_FILENAME
    path.write_text(
        "appearance:\n  theme: Purple\n  backdrop: 5\n  accent: red\n"
        "fonts:\n  latex_size: abc\nwindow:\n  x: nowhere\n",
        encoding="utf-8",
    )
    store = store_at(path)
    assert store.get("appearance.theme") == "Auto"
    assert store.get("appearance.backdrop") == "mica"
    assert store.get("appearance.accent") == DEFAULTS["appearance"]["accent"]
    assert store.get("fonts.latex_size") == 24
    assert store.get("window.x") is None


def test_accent_mode_is_validated_and_persisted():
    path = temp_dir() / CONFIG_FILENAME
    store = store_at(path)
    assert store.get("appearance.accent_mode") == "default"
    assert store.set("appearance.accent_mode", "nonsense") == "default"
    assert store.set("appearance.accent_mode", "system") == "system"
    assert store_at(path).get("appearance.accent_mode") == "system"


def test_a_config_from_before_accent_modes_keeps_its_colour():
    """Such a file applied `accent` directly, so it must not land on `default`."""
    path = temp_dir() / CONFIG_FILENAME
    path.write_text(
        "appearance:\n  theme: Dark\n  accent: '#ff8800'\n", encoding="utf-8"
    )
    store = store_at(path)
    assert store.get("appearance.accent_mode") == "custom"
    assert store.get("appearance.accent") == "#ff8800"


def test_numeric_values_are_clamped():
    path = temp_dir() / CONFIG_FILENAME
    store = store_at(path)
    assert store.set("fonts.latex_size", 999) == 96
    assert store.set("fonts.latex_size", 3) == 8
    assert store.set("fonts.code_size", 999) == 72
    assert store.set("fonts.code_size", 1) == 6
    assert store.set("fonts.keyboard_size", 0) == 6
    assert store.set("window.width", 10) == 860
    assert store.set("window.height", 999999) == 20000


def test_typography_defaults_are_cross_platform_preference_lists():
    """The defaults must name Windows, macOS and Linux faces and be lists."""
    from python.fonts import split_families

    fonts = DEFAULTS["fonts"]
    code = split_families(fonts["code_family"])
    keyboard = split_families(fonts["keyboard_family"])
    # A list, not one name: the list is what Qt resolves each character against,
    # and QML cannot express it (its `font` type has no `families`).
    assert len(code) > 3 and len(keyboard) > 3
    assert "monospace" in code and "serif" in keyboard
    assert any("Consolas" in n or "Cascadia" in n for n in code)              # Windows
    assert any("Menlo" in n or "Monaco" in n or "SF Mono" in n for n in code)  # macOS
    assert any(n.startswith("DejaVu") for n in code)                          # Linux
    assert fonts["latex_font"] == ""      # "" = ziamath's bundled STIX Two Math
    assert (fonts["code_size"], fonts["keyboard_size"], fonts["latex_size"]) == (14, 16, 24)


def test_font_family_keys_keep_the_preference_list_verbatim():
    path = temp_dir() / CONFIG_FILENAME
    store = store_at(path)
    typed = "NoSuchFont, Consolas, monospace"
    assert store.set("fonts.code_family", typed) == typed
    assert store_at(path).get("fonts.code_family") == typed
    # An empty list is not a choice, so it falls back rather than sticking.
    assert store.set("fonts.code_family", "   ") == DEFAULTS["fonts"]["code_family"]
    assert store.set("fonts.latex_font", "Cambria Math") == "Cambria Math"


def test_a_pre_fonts_config_keeps_its_latex_size():
    """`rendering.latex_size` only moved; a file written before it must migrate."""
    path = temp_dir() / CONFIG_FILENAME
    path.write_text("rendering:\n  latex_size: 40\n", encoding="utf-8")
    assert store_at(path).get("fonts.latex_size") == 40


def test_the_new_latex_size_wins_over_the_old_key():
    path = temp_dir() / CONFIG_FILENAME
    path.write_text(
        "rendering:\n  latex_size: 40\nfonts:\n  latex_size: 20\n", encoding="utf-8"
    )
    assert store_at(path).get("fonts.latex_size") == 20


def test_a_scalar_fonts_value_degrades_instead_of_crashing_the_migration():
    """A non-mapping ``fonts`` value must not replace the section: the old
    ``rendering.latex_size`` still migrates and the other fonts keys keep their
    defaults."""
    path = temp_dir() / CONFIG_FILENAME
    path.write_text("rendering:\n  latex_size: 40\nfonts: hello\n", encoding="utf-8")
    store = store_at(path)
    assert store.get("fonts.latex_size") == 40
    assert store.get("fonts.code_size") == DEFAULTS["fonts"]["code_size"]


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


def test_malformed_keyboard_yaml_never_breaks_startup():
    """A hand-edited layout — a list at the root, or a scalar tab — must fall
    back to the numeric keypad rather than raise at boot."""
    import python.keyboard_config as kc

    for doc in ("- a\n- b\n", "basic: hello\n"):
        path = temp_dir() / "keyboard_config.yaml"
        path.write_text(doc, encoding="utf-8")
        original = kc.KEYBOARD_CONFIG_PATH
        kc.KEYBOARD_CONFIG_PATH = path
        try:
            tabs = kc.load_keyboard_tabs()
        finally:
            kc.KEYBOARD_CONFIG_PATH = original
        assert tabs and tabs[0]["key"] == "basic" and tabs[0]["keys"]


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
    store.set("fonts.latex_size", 40)
    store.reset()
    assert store.values == DEFAULTS
    assert store_at(path).get("appearance.theme") == "Auto"


def test_portable_store_writes_into_the_data_dir():
    root = temp_dir()
    (root / "data").mkdir()
    store = SettingsStore.open(root, {}, "windows")
    assert store.is_portable is True
    store.set("appearance.theme", "Dark")
    assert (root / "data" / CONFIG_FILENAME).is_file()


def test_open_prefers_the_system_dir_without_a_data_dir():
    root = temp_dir()
    appdata = temp_dir()
    store = SettingsStore.open(root, {"APPDATA": str(appdata)}, "windows")
    assert store.is_portable is False
    assert store.path == appdata / "Symplify" / CONFIG_FILENAME


# --------------------------------------------------------------------------
# The accent: mode in effect vs. the colour the user picked
# --------------------------------------------------------------------------

def test_the_accents_variants_are_rgb_blends():
    """Ported from the C# ThemeColorCalculator: blends, not HSL steps."""
    from python.accent import (BLEND_FACTOR, black_blend, secondary, tertiary,
                               white_blend)

    # The blend definitions themselves.
    assert white_blend(0.0, 0.0, 0.0, 0.25) == (0.25, 0.25, 0.25)
    assert white_blend(1.0, 1.0, 1.0, 0.5) == (1.0, 1.0, 1.0)
    assert white_blend(0.2, 0.4, 0.6, 0.0) == (0.2, 0.4, 0.6)
    assert black_blend(0.8, 0.4, 0.2, 0.5) == (0.4, 0.2, 0.1)
    assert black_blend(0.0, 0.0, 0.0, 0.9) == (0.0, 0.0, 0.0)
    # The pair the palette is built from.
    assert secondary(0.2, 0.4, 0.6) == white_blend(0.2, 0.4, 0.6, BLEND_FACTOR)
    assert tertiary(0.2, 0.4, 0.6) == black_blend(0.2, 0.4, 0.6, BLEND_FACTOR)


def test_the_variant_trio_is_ordered_darkest_to_lightest():
    from python.accent import variants
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"appearance.accent_mode": "custom", "appearance.accent": "#0078d4"})
    vm = SettingsViewModel(store)
    darker, primary, lighter = variants("#0078d4")

    assert primary == "#0078d4"                     # the accent is its own primary
    assert darker == vm.accentForScheme(False)      # light theme takes the darker
    assert lighter == vm.accentForScheme(True)      # dark theme the lighter
    # Each step moves the way its name says. A channel already at 0 (the red of
    # #0078d4) cannot decrease, so the test is "no channel moves the wrong way,
    # and at least one moves".
    def channels(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    down = channels(darker), channels(primary)
    up = channels(lighter), channels(primary)
    assert all(d <= p for d, p in zip(*down)) and any(d < p for d, p in zip(*down))
    assert all(l >= p for l, p in zip(*up)) and any(l > p for l, p in zip(*up))


def test_the_tinted_gray_ramp_keeps_the_frameworks_properties():
    """Four of the C# suite's assertions, ported."""
    from python.accent import TINTED_GRAY_KEYS, tinted_grays

    grays = tinted_grays(0.0, 120 / 255, 215 / 255)
    assert len(grays) == 11 and tuple(grays) == TINTED_GRAY_KEYS
    # Monotonically darkening, lightest first, all channels in range.
    levels = [sum(grays[k]) for k in TINTED_GRAY_KEYS]
    assert levels == sorted(levels, reverse=True)
    assert all(0.0 <= c <= 1.0 for v in grays.values() for c in v)
    # A black accent gives genuinely neutral steps.
    neutral = tinted_grays(0.0, 0.0, 0.0)
    assert all(max(v) - min(v) < 0.01 for v in neutral.values())
    # Different hues tint the ramp differently.
    assert tinted_grays(0.0, 0.0, 1.0)["500"] != tinted_grays(1.0, 0.0, 0.0)["500"]


def test_accent_shading_clamps_and_tolerates_bad_input():
    from python.accent import for_scheme, variants

    assert for_scheme("#ffffff", dark=False) == "#bfbfbf"   # -25% blend
    assert for_scheme("#ffffff", dark=True) == "#ffffff"    # already white
    assert for_scheme("#000000", dark=False) == "#000000"
    assert for_scheme("not a colour", dark=True) == "not a colour"
    assert variants("not a colour") == ("not a colour",)


def test_shading_follows_one_rule_for_every_mode():
    """The same blend for default/system/custom, on any platform."""
    from python.accent import for_scheme
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"appearance.accent_mode": "custom", "appearance.accent": "#0078d4"})
    vm = SettingsViewModel(store)
    # Light takes the darker variant, dark the lighter — no mode is special.
    assert vm.accentForScheme(False) == for_scheme("#0078d4", False)
    assert vm.accentForScheme(True) == for_scheme("#0078d4", True)
    assert vm.accentForScheme(False) != vm.accentForScheme(True)

    vm.accentMode = "default"
    base = DEFAULTS["appearance"]["accent"]
    assert vm.accentForScheme(False) == for_scheme(base, False)
    assert vm.accentForScheme(True) == for_scheme(base, True)

    # `system` derives from the OS base the same way, so the app behaves
    # identically on platforms whose toolkit offers no per-scheme accent at all.
    vm.accentMode = "system"
    assert vm.accentForScheme(False) == for_scheme(vm.accent, False)
    assert vm.accentForScheme(True) == for_scheme(vm.accent, True)


def test_the_shading_switch_turns_the_finetuning_off():
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"appearance.accent_mode": "custom", "appearance.accent": "#0078d4"})
    vm = SettingsViewModel(store)
    assert vm.accentShading is True                 # on by default

    vm.accentShading = False
    # Off: the colour verbatim, in both schemes.
    assert vm.accentForScheme(False) == vm.accentForScheme(True) == "#0078d4"
    assert store.get("appearance.accent_shading") is False

    vm.accentShading = True
    assert vm.accentForScheme(True) != "#0078d4"


def test_the_preview_strip_shows_the_variant_trio_or_the_flat_colour():
    """What the swatches beside the colour dropdown show, per switch state."""
    from python.accent import variants
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"appearance.accent_mode": "custom", "appearance.accent": "#0078d4"})
    vm = SettingsViewModel(store)
    assert vm.accentPreview == list(variants("#0078d4"))
    assert len(vm.accentPreview) == 3          # tertiary, primary, secondary

    vm.accentShading = False
    assert vm.accentPreview == ["#0078d4"]     # one flat swatch
    # It follows the accent in use, not the stored custom colour: in `system`
    # mode the stored colour is irrelevant.
    vm.accentMode = "system"
    assert vm.accentPreview == [vm.accent]


def test_the_picked_colour_updates_at_once_but_writes_lazily():
    """A picker drag emits per mouse move; the disk write must not follow it.

    The timer itself is asserted rather than awaited: this suite has no event
    loop (and creating one would install an application other tests' palette
    lookups would then see), so the flush is invoked directly, which is exactly
    what the timer's timeout would do.
    """
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    vm = SettingsViewModel(store)
    original = store.get("appearance.accent")

    for step in ("#ff0000", "#00ff00", "#0000ff", "#ffff00"):
        vm.customAccent = step
        # In effect immediately — the accent applies live, the preview follows…
        assert vm.customAccent == step
        # …and nothing is written yet; the value waits in the viewmodel.
        # (The timer itself cannot be asserted here: QTimer.start() does not
        # activate without an application, so the real firing is covered by the
        # app probe instead.)
        assert vm._pending_accent == step
        assert store.get("appearance.accent") == original

    vm._flush_pending_accent()          # what the timer firing does
    assert store.get("appearance.accent") == "#ffff00"
    assert store_at(temp_dir() / CONFIG_FILENAME) is not None   # still readable
    vm._flush_pending_accent()          # idempotent: nothing pending any more
    assert store.get("appearance.accent") == "#ffff00"

    # An invalid colour is still ignored outright.
    vm.customAccent = "not a colour"
    assert vm.customAccent == "#ffff00"


def test_the_os_finetuning_option_states_its_conditions():
    """Windows only, system accent, shading on — and it needs captured values."""
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"appearance.accent_mode": "custom"})
    vm = SettingsViewModel(store)

    # On Windows the option exists (whether it is usable is separate)...
    assert vm.accentOsShadingSupported is True
    # ...but not while another accent mode is selected.
    assert vm.accentOsShadingAvailable is False
    vm.accentMode = "system"
    # Headless there is no palette, so the OS values were never captured: even
    # with all three conditions met there is nothing to prefer.
    assert vm.accentOsShadingAvailable is False

    vm.accentShading = False
    assert vm.accentOsShadingAvailable is False
    vm.accentShading = True
    # The stored preference itself is independent of availability.
    assert vm.accentOsShading is True                # on by default
    vm.accentOsShading = False
    assert store.get("appearance.accent_os_shading") is False


def test_os_finetuning_off_falls_back_to_the_blend():
    """Turning it off must change which accent is applied, not just be stored."""
    from python.accent import for_scheme
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"appearance.accent_mode": "system"})
    vm = SettingsViewModel(store)
    for dark in (False, True):
        # With no OS values available the blend is what is applied either way.
        assert vm.accentForScheme(dark) == for_scheme(vm.accent, dark)
    vm.accentOsShading = False
    for dark in (False, True):
        assert vm.accentForScheme(dark) == for_scheme(vm.accent, dark)


def test_accent_mode_decides_the_colour_in_effect():
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    vm = SettingsViewModel(store)
    assert vm.accentMode == "default"
    assert vm.accent == DEFAULTS["appearance"]["accent"]

    vm.customAccent = "#ff8800"                 # stored, but not in effect yet
    assert vm.customAccent == "#ff8800"
    assert vm.accent == DEFAULTS["appearance"]["accent"]

    vm.accentMode = "custom"
    assert vm.accent == "#ff8800"

    vm.accentMode = "default"                   # the pick survives a mode change
    assert vm.accent == DEFAULTS["appearance"]["accent"]
    vm.accentMode = "custom"
    assert vm.accent == "#ff8800"


def test_system_accent_does_not_use_the_custom_colour():
    """`system` reads the palette, so whatever was picked must not leak in."""
    from PySide6.QtGui import QColor

    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"appearance.accent": "#ff8800", "appearance.accent_mode": "system"})
    vm = SettingsViewModel(store)
    assert QColor(vm.accent).isValid()
    assert vm.accent != "#ff8800"


def test_an_invalid_picked_colour_is_ignored():
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    vm = SettingsViewModel(store)
    vm.customAccent = "not a colour"
    assert vm.customAccent == DEFAULTS["appearance"]["accent"]


def test_reset_discards_a_pending_accent_write():
    """A pick that settled moments before reset must not fire after it and
    resurrect the colour the user just wiped."""
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    vm = SettingsViewModel(store)
    vm.customAccent = "#ff0000"          # pending, not yet written
    assert vm._pending_accent == "#ff0000"
    vm.resetToDefaults()
    assert vm._pending_accent is None
    vm._flush_pending_accent()           # what the timer would do after reset
    assert store.get("appearance.accent") == DEFAULTS["appearance"]["accent"]
    assert vm.customAccent == DEFAULTS["appearance"]["accent"]


# --------------------------------------------------------------------------
# Font resolution. Needs a real QApplication (QFontDatabase aborts without one
# rather than raising, and glyph coverage has to be measured), so it runs in a
# subprocess like the bootstrap tests.
# --------------------------------------------------------------------------

FONT_SCRIPT = r"""
import pathlib, sys, tempfile
from PySide6.QtWidgets import QApplication
from python.settings import SettingsStore
from python.viewmodel.settings_viewmodel import SettingsViewModel

app = QApplication(sys.argv)
store = SettingsStore(pathlib.Path(tempfile.mkdtemp()) / "config.yaml")
store.load()
vm = SettingsViewModel(store)

# The font handed to QML carries the whole list, which is what lets Qt resolve
# each character against the next family (a real per-character fallback).
vm.codeFamily = "Consolas, Cambria"
print("CHAIN", "|".join(vm.codeFont.families()))
print("SIZE", vm.codeFont.pixelSize())

# An uninstalled name is skipped for display, but stays in the font Qt gets.
vm.codeFamily = "NoSuchFont_XYZ, Consolas"
print("DISPLAY", vm.codeFontFamily)
print("KEPT", "|".join(vm.codeFont.families()))

# Keyboard coverage is where a gap would actually show: the layout has ∛, which
# Consolas lacks and Cambria has. A gap in the primary face is covered by the
# fallback; a glyph no family has is reported.
vm.keyboardFamily = "Consolas, Cambria"
print("COVERED", repr(vm.keyboardMissingGlyphs))
vm.keyboardFamily = "Consolas"
print("UNCOVERED", repr(vm.keyboardMissingGlyphs))

# Generic keywords expand into real families (Qt cannot look up "monospace")
# and their extra members are counted as fallbacks.
vm.keyboardFamily = "serif"
print("KEYWORD_COUNT", vm.keyboardFallbackCount)

# The shipped default covers every glyph the layout shows.
vm.keyboardFamily = ""
print("DEFAULT", vm.keyboardFontFamily)
print("COUNT", vm.keyboardFallbackCount)
print("MISSING", repr(vm.keyboardMissingGlyphs))
"""


def run_font_script() -> dict:
    """Run the font-resolution report in a fresh interpreter (needs a QApplication)."""
    env = {**os.environ}
    env.pop("QT_QPA_PLATFORM", None)
    result = subprocess.run(
        [sys.executable, "-c", FONT_SCRIPT],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr
    report = {}
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if parts and parts[0].isupper():
            report[parts[0]] = parts[1].strip("'\"") if len(parts) > 1 else ""
    return report


def test_the_font_handed_to_qml_carries_the_whole_family_list():
    """Qt only falls back per character when it receives the list, not one name."""
    report = run_font_script()
    assert report["CHAIN"] == "Consolas|Cambria"
    assert report["SIZE"] == "14"
    # An uninstalled name is skipped for *display* but still passed to Qt, which
    # simply skips it during lookup.
    assert report["DISPLAY"] == "Consolas"
    assert report["KEPT"] == "NoSuchFont_XYZ|Consolas"


def test_a_glyph_missing_from_one_face_is_covered_by_the_next():
    """The point of fallback: the keyboard needs ∛, Consolas lacks it, Cambria has it."""
    report = run_font_script()
    assert report["COVERED"] == ""
    assert report["UNCOVERED"] == "∛"      # nothing in that list can draw it


def test_the_default_font_chains_cover_what_they_typeset():
    report = run_font_script()
    assert report["DEFAULT"] != ""
    assert int(report["MISSING"] == "")    # the shipped chain has no gaps
    # A generic keyword expands into real families, which is why the default of
    # either row ships more than one name and still needs no coverage warning.
    assert int(report["KEYWORD_COUNT"]) > 0
    assert int(report["COUNT"]) > 0


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
# What the window does with the remembered geometry — position only, since the
# size is declarative (see _restore_geometry)
# --------------------------------------------------------------------------

class FakeWindow(QObject):
    """Just enough of a QQuickWindow for the geometry logic, with no Qt app."""

    widthChanged = Signal()
    heightChanged = Signal()
    xChanged = Signal()
    yChanged = Signal()
    visibleChanged = Signal()
    closing = Signal()

    def __init__(self):
        super().__init__()
        self._props = {"visible": True, "width": 1180, "height": 760, "x": 0, "y": 0}
        self.maximized = False

    def setProperty(self, name, value):
        self._props[name] = value

    def property(self, name):
        return self._props.get(name)

    def showMaximized(self):
        self.maximized = True

    def windowState(self):
        return Qt.WindowState.WindowNoState


def window_with(store_values):
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"window.remember": True, **store_values})
    window = FakeWindow()
    SettingsViewModel(store).attachWindow(window)
    return window


def test_windowed_restore_applies_the_remembered_position():
    window = window_with({"window.maximized": False, "window.x": 250, "window.y": 180})
    assert (window.property("x"), window.property("y")) == (250, 180)
    assert window.maximized is False


def test_maximized_restore_leaves_the_position_to_the_platform():
    """Such a window must not jump to an old spot when dragged out of fullscreen."""
    window = window_with({"window.maximized": True, "window.x": 250, "window.y": 180})
    assert (window.property("x"), window.property("y")) == (0, 0)   # untouched


def test_turning_remember_on_mid_session_starts_tracking():
    """attachWindow skips the wiring when remember is off at startup; turning it
    on later must start tracking, or the final geometry is silently lost."""
    from python.viewmodel.settings_viewmodel import SettingsViewModel

    store = store_at(temp_dir() / CONFIG_FILENAME)
    store.update({"window.remember": False})
    vm = SettingsViewModel(store)
    window = FakeWindow()
    vm.attachWindow(window)               # off at startup -> no wiring
    vm.rememberWindow = True              # turn on mid-session
    window.setProperty("width", 900)
    window.setProperty("height", 600)
    window.closing.emit()                 # what Window.closing does on quit
    assert store.get("window.width") == 900
    assert store.get("window.height") == 600


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
print("ACCENT_MODE", settings.get("appearance.accent_mode"))
print("RINUI", json.dumps(RinConfig.config, sort_keys=True))
RinConfig["theme"] = {"current_theme": "Light"}       # must not touch disk
RinConfig.upload_config("theme_color", "#000000")
print("ROOT_ENTRIES", sorted(p.name for p in root.iterdir()))
# nothing RinUI-shaped anywhere: the import ran in a scratch directory
print("CONFIG_DIR_ENTRIES", sorted(p.name for p in settings.path.parent.iterdir()))
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
    assert report["ACCENT_MODE"] == "custom"   # a real pick arrives as one
    assert str(appdata) in report["STORE"]
    # RinUI runs on our values but can no longer persist anything
    assert '"current_theme": "Dark"' in report["RINUI"]
    assert '"backdrop_effect": "acrylic"' in report["RINUI"]
    assert report["CONFIG_DIR_ENTRIES"] == "['config.yaml']"
    assert report["WINDOW"] == "RinUIWindow"
    assert report["VERSION"].count(".") >= 1


def test_bootstrap_keeps_default_mode_for_a_default_coloured_legacy_accent():
    """A legacy colour equal to RinUI's own default was never a pick, so the
    migration must leave the mode on `default` instead of pinning `custom`."""
    root = temp_dir()
    appdata = temp_dir()
    legacy = root / "RinUI" / "config"
    legacy.mkdir(parents=True)
    (legacy / "rin_ui.json").write_text(json.dumps({
        "theme_color": DEFAULTS["appearance"]["accent"],
    }), encoding="utf-8")

    report = run_bootstrap(root, appdata)
    assert report["ACCENT_MODE"] == "default"


def test_bootstrap_leaves_the_launch_dir_clean_without_a_legacy_config():
    root = temp_dir()
    appdata = temp_dir()
    report = run_bootstrap(root, appdata)
    assert report["ROOT_ENTRIES"] == "[]"
    assert report["CONFIG_DIR_ENTRIES"] == "['config.yaml']"
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
