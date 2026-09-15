# coding: utf-8
"""Accent palette generation (pure Python, zero Qt).

Ported from the C# ``ThemeColorCalculator`` in the I-Synergy Framework, released
under the MIT License:

* source — https://dev.azure.com/i-synergy/I-Synergy.Framework/_git/I-Synergy.Framework?path=%2Ftests%2FISynergy.Framework.UI.Tests%2FUtilities%2FThemeColorCalculatorTests.cs
* license — https://dev.azure.com/i-synergy/_git/I-Synergy.Framework?path=/LICENSE

The accent's variants are RGB **blends** rather than HSL steps. ``white_blend``
mixes towards white by a factor, ``black_blend`` scales towards black, and the
palette is the trio ``tertiary`` (darker, -25%) / ``primary`` / ``secondary``
(lighter, +25%).
Each blend is monotonic and clamped by construction, which is why the tests for
it read as properties rather than expected values.

Why it is applied this way:

* The **light theme takes ``tertiary``** and the **dark theme ``secondary``**,
  which is the framework's own primary/secondary/tertiary semantics — a variant
  that reads on a light background, and one that reads on a dark one. Windows
  moves in the same directions (its light accent is darker than the base, its
  dark accent lighter), which is what the shape of the palette has in common with
  it.
* A base colour that is already tuned for a scheme must **not** be used here, or
  the light variant would be darkened twice. So the ``system`` accent is read as
  the OS *base* accent, not as the OS's light-theme accent: ``QPalette.Highlight``
  under the dark scheme is the base (confirmed against the OS on two accents),
  and ``QPalette.Accent`` is the per-scheme value.

**How faithful this is to Windows, measured** (Windows: base → light / dark):

| accent | Windows light | our tertiary | Windows dark | our secondary |
|---|---|---|---|---|
| teal `#258292` | `#1d6978` | `#1c626e` | `#71d4db` | `#5ca1ad` |
| blue `#0078d4` | `#0067c0` | `#005a9f` | `#4cc2ff` | `#409adf` |

The light variant lands close (the framework's 25% darkening against Windows'
measured ~20% and ~12%). The dark one does not: a white blend raises the minimum
channel, so it **desaturates** (teal S 59.6 → 33.1) where Windows preserves
saturation exactly and lifts lightness further (L 35.9 → 65.1). No single blend
factor reaches Windows' dark value — the per-channel factors it would need are
0.349/0.656/0.670 and 0.298/0.548/1.000, i.e. it is not a white blend at all.

``tinted_grays`` is the other half of that framework (an 11-step neutral ramp
tinted by the accent's hue, driving Background/Surface/Control per theme). It is
not wired here because RinUI owns this app's neutrals; using it would mean
overriding RinUI's colour roles wholesale.
"""

from typing import Dict, Tuple

#: How far ``secondary`` blends towards white and ``tertiary`` towards black.
BLEND_FACTOR = 0.25

#: How much of the accent leaks into the neutral ramp.
TINT = 0.04

#: The neutral ramp's keys, lightest to darkest.
TINTED_GRAY_KEYS = (
    "000", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950",
)

Rgb = Tuple[float, float, float]


def _parse(color: str) -> Rgb:
    """``'#rrggbb'`` as three 0..1 channels, or raise ValueError."""
    text = str(color or "").strip()
    if len(text) != 7 or not text.startswith("#"):
        raise ValueError(f"not a #rrggbb colour: {color!r}")
    try:
        value = int(text[1:], 16)
    except ValueError:
        raise ValueError(f"not a #rrggbb colour: {color!r}") from None
    return ((value >> 16 & 0xFF) / 255, (value >> 8 & 0xFF) / 255,
            (value & 0xFF) / 255)


def _hex(rgb: Rgb) -> str:
    """Three 0..1 channels as ``'#rrggbb'``, rounded and clamped."""
    return "#%02x%02x%02x" % tuple(
        round(max(0.0, min(1.0, channel)) * 255) for channel in rgb
    )


def white_blend(red: float, green: float, blue: float, factor: float) -> Rgb:
    """Blend towards white by ``factor`` (0 keeps the colour, 1 gives white)."""
    return (red + (1 - red) * factor, green + (1 - green) * factor,
            blue + (1 - blue) * factor)


def black_blend(red: float, green: float, blue: float, factor: float) -> Rgb:
    """Blend towards black by ``factor`` (0 keeps the colour, 1 gives black)."""
    return (red * (1 - factor), green * (1 - factor), blue * (1 - factor))


def secondary(red: float, green: float, blue: float) -> Rgb:
    """The lighter variant — the framework's ``CalculateSecondary``."""
    return white_blend(red, green, blue, BLEND_FACTOR)


def tertiary(red: float, green: float, blue: float) -> Rgb:
    """The darker variant — the framework's ``CalculateTertiary``."""
    return black_blend(red, green, blue, BLEND_FACTOR)


def tinted_grays(red: float, green: float, blue: float) -> Dict[str, Rgb]:
    """An 11-step neutral ramp carrying a trace of the accent's hue.

    Lightest first (``000``) to darkest (``950``). Each step is a neutral level
    with a small amount of the accent mixed in, so a black or white accent yields
    genuinely neutral steps (equal channels) while any other accent leaves a
    visible cast. Not consumed by this app (see the module docstring), but part of
    the framework being ported.
    """
    last = len(TINTED_GRAY_KEYS) - 1
    return {
        key: tuple(
            (1.0 - index / last) * (1 - TINT) + channel * TINT
            for channel in (red, green, blue)
        )
        for index, key in enumerate(TINTED_GRAY_KEYS)
    }


def for_scheme(color: str, dark: bool) -> str:
    """The accent variant for a light or dark theme.

    Dark takes the lighter ``secondary``, light the darker ``tertiary``. Falls
    back to the input on a malformed colour so a bad value cannot blank the
    accent.
    """
    try:
        rgb = _parse(color)
    except ValueError:
        return color
    return _hex(secondary(*rgb) if dark else tertiary(*rgb))


def variants(color: str) -> Tuple[str, ...]:
    """The palette as ``(tertiary, primary, secondary)`` — darkest to lightest.

    The order the framework's own preview uses, and what the settings page's
    swatch strip shows when shading is on.
    """
    try:
        rgb = _parse(color)
    except ValueError:
        return (color,)
    return (_hex(tertiary(*rgb)), color, _hex(secondary(*rgb)))
