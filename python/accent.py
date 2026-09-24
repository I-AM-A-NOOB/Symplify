# coding: utf-8
"""The accent shades Windows derives from a chosen colour (pure Python, zero Qt).

Windows does not paint the accent colour it is handed. It derives a ramp of seven
shades from it and paints with those — ``#258292`` shows up as ``#1d6978`` in
light mode and ``#71d4db`` in dark — and this module reproduces that derivation.

Ported from ``windowsthemefinetuner``, this app author's own package (its
``palette`` and ``colorspace`` modules, folded into one file here). That project
is the reference implementation and carries the full recorded corpus; this module
is the copy this app ships, so the app keeps agreeing with it.

Provenance
    The behaviour is Windows-specific and was characterised **observationally**:
    colours were pushed through the shell's accent preference (``uxtheme.dll``
    ordinals 120/122) and the ramp the shell published in
    ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Accent!AccentPalette``
    was read back — a few thousand times, of which 484 are pinned as recorded
    vectors in the reference project and a documented sample of those is in
    ``tests/golden_accent_palettes.json`` here.

    **No Microsoft source, binary or resource is reproduced or redistributed.**
    The arithmetic is published standards — the sRGB transfer function, 8-bit
    quantisation and tristimulus matrices of IEC 61966-2-1, and CIELAB per CIE 15
    under the D65 white point — and the numeric parameters below, which are the
    behaviour of an interface rather than copied expression.

The ramp
    Two code paths exist and the shell picks between them per colour. Both take
    the accent to a fixed *lightness* and spread the other six entries around it;
    they differ in the space that happens in, and so in how the hue drifts once
    the result is expressed back in sRGB.

    **Lab path** (ordinary colours: ``HSL L`` inside ``0.25..0.75``, saturation at
    least ``0.15``). Hue and chroma survive exactly and only ``L*`` moves::

        base = Lab(50, a*, b*)   high = Lab(100, a*, b*)   low = Lab(0, a*, b*)
        light1..3 = lerp(base, high, t)     t = 0.16 / 0.58 / 0.82
        dark1..3  = lerp(low, base,  t)     t = 0.78 / 0.50 / 0.18

    Each lerp is rebuilt through HSL with its saturation floored at the base's,
    which is why the hue drift that comes back in sRGB is a property of the
    colour space rather than of an extra adjustment.

    **HSL path** (colours at the ends of the lightness range, or near-neutral
    ones). Hue and saturation are kept verbatim and only ``L`` moves, by a fixed
    fraction of its distance from mid-grey: ``0.68 / 0.40 / 0.20`` either side.

Fidelity (measured against the shell, in the reference project)
    * Lab path: byte-exact, without exception (624/624 live).
    * HSL path: every entry within one unit, exactly equal on about two thirds.
    * Tail: roughly one channel in 1700 lands within an ulp of a ``.5`` boundary,
      where the shell's arithmetic and double precision part ways.
    * The value *stored* in ``AccentPalette`` can differ by one unit from
      recomputing the same accent, most likely because it was written whenever the
      accent was last set. This module reproduces the recomputation. The two
      entries the schemes actually paint with agree either way — which is why the
      ``system`` accent on Windows still prefers the value the OS reports itself
      over deriving it here.

Superseded
    This replaces a port of the I-Synergy ``ThemeColorCalculator`` (MIT) that this
    module carried: its 25% blend towards black or white was measurably not what
    Windows does. Light landed close by accident, dark did not at all — a blend
    towards white raises the minimum channel, so it **desaturates** (teal
    S 59.6 -> 33.1) where Windows preserves saturation and lifts lightness
    (L 35.9 -> 65.1), and no single blend factor reaches it.
"""

from typing import NamedTuple, Tuple

#: ``(r, g, b)``, one byte per channel.
Rgb = Tuple[int, int, int]

#: White point of the sRGB primaries, scaled so that ``Y`` spans 0..100.
_WHITE = (95.047, 100.0, 108.883)

#: CIE 15 lightness constants.
_LAB_EPSILON = 216 / 24389   # (6/29) ** 3: where f() switches to a cube root
_LAB_KAPPA = 841 / 108       # (29/3) ** 3
_LAB_DELTA = 4 / 29
_LAB_DIVISOR = 116.0
_LAB_OFFSET = 16.0
_LAB_SCALE_A = 500.0
_LAB_SCALE_B = 200.0
_U8 = 255.0
_ONE_THIRD = 1 / 3

#: L* window the Lab path normalises the accent into. Two constants, so a colour
#: already inside the window keeps its own lightness, to within rounding.
LAB_L_MIN = 49.0
LAB_L_MAX = 50.0

#: The lightness window the HSL path uses, and the saturation below which the HSL
#: path takes over even inside that window.
HSL_L_MIN = 0.25
HSL_L_MAX = 0.75
HSL_S_MIN = 0.15

#: ``(entry index, anchor, factor)`` for the Lab path's six lerps.
LAB_LERP_FACTORS = (
    (0, "high", 0.82),
    (1, "high", 0.58),
    (2, "high", 0.16),
    (4, "low", 0.78),
    (5, "low", 0.50),
    (6, "low", 0.18),
)

#: ``(entry index, direction, factor)`` for the HSL path's six offsets.
HSL_LIGHTNESS_STEPS = (
    (0, +1, 0.68),
    (1, +1, 0.40),
    (2, +1, 0.20),
    (4, -1, 0.20),
    (5, -1, 0.40),
    (6, -1, 0.68),
)

#: The ramp, lightest to darkest; index 3 is the accent itself.
ENTRY_NAMES = ("light3", "light2", "light1", "accent", "dark1", "dark2", "dark3")

#: Which entry the shell paints with when the system is in light resp. dark mode.
LIGHT_MODE_INDEX = 4        # dark1
DARK_MODE_INDEX = 1         # light2


class _Lab(NamedTuple):
    """CIE L*a*b*: ``L`` in 0..100, ``a``/``b`` signed, ``0`` is neutral."""

    L: float
    a: float
    b: float


class _Hsl(NamedTuple):
    """HSL with ``h`` in turns (0..1), ``s`` and ``l`` in 0..1."""

    h: float
    s: float
    l: float


# --- sRGB / CIELAB / HSL primitives ---------------------------------------
#
# The expressions are written out rather than folded into generic matrix helpers:
# floating-point evaluation order decides the last bit, and the last bit decides
# whether a channel comes out one unit higher. This order is the one that
# reproduces the shell's own output.

def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else min(value, high)


def _decode(channel: int) -> float:
    """An sRGB byte as linear light, 0..1 — IEC 61966-2-1."""
    c = channel / _U8
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _encode(value: float) -> float:
    """Linear light, 0..1, as sRGB."""
    value = _clamp(value, 0.0, 1.0)
    return 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055


def _lab_f(t: float) -> float:
    return t ** _ONE_THIRD if t > _LAB_EPSILON else _LAB_KAPPA * t + _LAB_DELTA


def _lab_f_inverse(t: float) -> float:
    cube = t ** 3
    return cube if cube > _LAB_EPSILON else (t - _LAB_DELTA) / _LAB_KAPPA


def _quantise_half_up(value: float) -> int:
    """0..1 as a byte, halves up — the Lab path's quantiser."""
    return int(_clamp(value, 0.0, 1.0) * _U8 + 0.5)


def _rgb_to_lab(rgb: Rgb) -> _Lab:
    lin_r, lin_g, lin_b = (_decode(c) for c in rgb)
    x = (0.4124 * lin_r + 0.3576 * lin_g + 0.1805 * lin_b) * 100.0
    y = (0.2126 * lin_r + 0.7152 * lin_g + 0.0722 * lin_b) * 100.0
    z = (0.0193 * lin_r + 0.1192 * lin_g + 0.9505 * lin_b) * 100.0
    fx = _lab_f(x / _WHITE[0])
    fy = _lab_f(y / _WHITE[1])
    fz = _lab_f(z / _WHITE[2])
    return _Lab(
        _LAB_DIVISOR * fy - _LAB_OFFSET,
        _LAB_SCALE_A * (fx - fy),
        _LAB_SCALE_B * (fy - fz),
    )


def _lab_to_rgb(lab: _Lab) -> Rgb:
    """CIELAB back to sRGB bytes; out-of-gamut results clip, as the shell's do."""
    fy = (lab.L + _LAB_OFFSET) / _LAB_DIVISOR
    fx = lab.a / _LAB_SCALE_A + fy
    fz = fy - lab.b / _LAB_SCALE_B
    x = _WHITE[0] * _lab_f_inverse(fx) / 100.0
    y = _WHITE[1] * _lab_f_inverse(fy) / 100.0
    z = _WHITE[2] * _lab_f_inverse(fz) / 100.0
    r = 3.2406 * x - 1.5372 * y - 0.4986 * z
    g = -0.9689 * x + 1.8758 * y + 0.0415 * z
    b = 0.0557 * x - 0.2040 * y + 1.0570 * z
    return (
        _quantise_half_up(_encode(r)),
        _quantise_half_up(_encode(g)),
        _quantise_half_up(_encode(b)),
    )


def _rgb_to_hsl(rgb: Rgb) -> _Hsl:
    r, g, b = (c / _U8 for c in rgb)
    high, low = max(r, g, b), min(r, g, b)
    chroma = high - low
    lightness = (high + low) / 2
    if chroma == 0:
        return _Hsl(0.0, 0.0, lightness)
    saturation = chroma / (2 - high - low) if lightness > 0.5 else chroma / (high + low)
    if high == r:
        hue = ((g - b) / chroma) % 6
    elif high == g:
        hue = (b - r) / chroma + 2
    else:
        hue = (r - g) / chroma + 4
    return _Hsl(hue / 6, saturation, lightness)


def _sector_channels(hsl: _Hsl) -> Tuple[float, float, float]:
    """HSL as three sRGB values in 0..255, before any quantisation.

    The sextant tuple is written literally and in this order on purpose: it is the
    expression the OS evaluates, and reordering the additions (through a weights
    table, say) shifts the last bit and hence some bytes.
    """
    chroma = (1 - abs(2 * hsl.l - 1)) * hsl.s
    sextant = (hsl.h * 6) % 6
    middle = chroma * (1 - abs(sextant % 2 - 1))
    minimum = hsl.l - chroma / 2
    r, g, b = (
        (chroma, middle, 0.0),
        (middle, chroma, 0.0),
        (0.0, chroma, middle),
        (0.0, middle, chroma),
        (middle, 0.0, chroma),
        (chroma, 0.0, middle),
    )[int(sextant) % 6]
    return (r + minimum, g + minimum, b + minimum)


def _hsl_to_rgb(hsl: _Hsl) -> Rgb:
    """HSL to bytes, halves up — the Lab path's quantiser."""
    r, g, b = _sector_channels(hsl)
    return (_quantise_half_up(r), _quantise_half_up(g), _quantise_half_up(b))


def _hsl_to_rgb_truncated(hsl: _Hsl) -> Rgb:
    """HSL to bytes, fractions discarded — the HSL path's quantiser.

    Measured against the shell, truncating this conversion reproduces 99 of the
    161 recorded HSL ramps exactly where rounding manages 88 — so the two paths
    quantise differently, and this is not a detail to tidy away.
    """
    r, g, b = _sector_channels(hsl)
    return (int(_clamp(r, 0.0, 1.0) * _U8), int(_clamp(g, 0.0, 1.0) * _U8),
            int(_clamp(b, 0.0, 1.0) * _U8))


def _lerp_rounded(first: Rgb, second: Rgb, t: float) -> Rgb:
    """Per-channel byte interpolation, halves up: ``first * (1 - t) + second * t``."""
    return (
        int(first[0] * (1 - t) + second[0] * t + 0.5),
        int(first[1] * (1 - t) + second[1] * t + 0.5),
        int(first[2] * (1 - t) + second[2] * t + 0.5),
    )


# --- the two ramps ---------------------------------------------------------

def uses_lab_pipeline(rgb: Rgb) -> bool:
    """Whether the shell would take the Lab path for this accent colour."""
    hsl = _rgb_to_hsl(rgb)
    return HSL_L_MIN <= hsl.l <= HSL_L_MAX and hsl.s >= HSL_S_MIN


def _lab_ramp(rgb: Rgb) -> Tuple[Rgb, ...]:
    lab = _rgb_to_lab(rgb)
    accent = _lab_to_rgb(lab._replace(L=_clamp(lab.L, LAB_L_MIN, LAB_L_MAX)))
    anchors = {
        "high": _lab_to_rgb(lab._replace(L=100.0)),
        "low": _lab_to_rgb(lab._replace(L=0.0)),
    }
    saturation_floor = _rgb_to_hsl(accent).s

    ramp = [accent] * len(ENTRY_NAMES)
    for index, anchor, factor in LAB_LERP_FACTORS:
        partner = anchors[anchor]
        first, second = (accent, partner) if anchor == "high" else (partner, accent)
        hue, saturation, lightness = _rgb_to_hsl(_lerp_rounded(first, second, factor))
        ramp[index] = _hsl_to_rgb(
            _Hsl(hue, max(saturation, saturation_floor), lightness)
        )
    return tuple(ramp)


def _hsl_ramp(rgb: Rgb) -> Tuple[Rgb, ...]:
    hue, saturation, lightness = _rgb_to_hsl(rgb)
    lightness = _clamp(lightness, HSL_L_MIN, HSL_L_MAX)
    reach = abs(lightness - 0.5)

    ramp = [_hsl_to_rgb_truncated(_Hsl(hue, saturation, lightness))] * len(ENTRY_NAMES)
    for index, direction, factor in HSL_LIGHTNESS_STEPS:
        shifted = _clamp(lightness + direction * factor * reach, 0.0, 1.0)
        ramp[index] = _hsl_to_rgb_truncated(_Hsl(hue, saturation, shifted))
    return tuple(ramp)


def palette(rgb: Rgb) -> Tuple[Rgb, ...]:
    """The seven accent shades for ``rgb``, ordered light3 .. dark3."""
    return _lab_ramp(rgb) if uses_lab_pipeline(rgb) else _hsl_ramp(rgb)


# --- what the app consumes -------------------------------------------------

def _parse(color: str) -> Rgb:
    """``'#rrggbb'`` as three bytes, or raise ValueError."""
    text = str(color or "").strip()
    if len(text) != 7 or not text.startswith("#"):
        raise ValueError(f"not a #rrggbb colour: {color!r}")
    try:
        value = int(text[1:], 16)
    except ValueError:
        raise ValueError(f"not a #rrggbb colour: {color!r}") from None
    return (value >> 16 & 0xFF, value >> 8 & 0xFF, value & 0xFF)


def _hex(rgb: Rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def for_scheme(color: str, dark: bool) -> str:
    """The accent shade for a light or dark theme.

    Light mode paints with the ramp's ``dark1`` and dark mode with ``light2`` — the
    two entries the shell itself uses — so a light theme gets the darker shade and
    a dark theme the lighter one. A malformed colour falls back to the input, so a
    bad value cannot blank the accent.
    """
    try:
        rgb = _parse(color)
    except ValueError:
        return color
    return _hex(palette(rgb)[DARK_MODE_INDEX if dark else LIGHT_MODE_INDEX])


def variants(color: str) -> Tuple[str, ...]:
    """The trio the preview strip shows, darkest to lightest.

    The two shades the schemes paint with around the accent itself: the ramp's
    ``dark1``, the colour as given, and its ``light2``.
    """
    try:
        rgb = _parse(color)
    except ValueError:
        return (color,)
    ramp = palette(rgb)
    return (_hex(ramp[LIGHT_MODE_INDEX]), color, _hex(ramp[DARK_MODE_INDEX]))
