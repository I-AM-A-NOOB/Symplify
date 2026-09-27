# coding: utf-8
"""LaTeX -> SVG rendering via ziamath.

Qt's QSvgRenderer ignores ``<use>`` transforms, so ziamath's default SVG2
output (symbol + use) renders blank/clipped. Setting ``svg2 = False``
embeds the glyph paths directly, which Qt renders correctly.
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import quote

from ziamath.config import config as zconfig

zconfig.svg2 = False

_SVG_WIDTH_RE = re.compile(r'width="([\d.]+)"')
_SVG_HEIGHT_RE = re.compile(r'height="([\d.]+)"')


def latex_to_svg(
    latex: str,
    size: Optional[float] = None,
    color: Optional[str] = None,
    font: Optional[str] = None,
) -> str:
    """Render a LaTeX string to an SVG string, or ``''`` if it cannot be parsed.

    Args:
        latex: The LaTeX source.
        size: Optional font size in points; ziamath's own default (24) is used
            when None.
        color: Optional text color (any CSS color, e.g. ``'#ffffff'``);
            ziamath defaults to black when None.
        font: Optional path to a font **file** containing a MATH typesetting
            table (see ``python/fonts.py``); None uses ziamath's bundled STIX Two
            Math. ziamath takes a file, not a family, and fails outright on a
            font without a MATH table rather than falling back to another one.
    """
    try:
        from ziamath.zmath import Latex

        kwargs = {}
        if size is not None:
            kwargs["size"] = size
        if color is not None:
            kwargs["color"] = color
        if font:
            kwargs["font"] = font
        return Latex(latex, **kwargs).svg()
    except Exception:
        return ""


#: The prefix every surface hands to QML's `Image`.
_DATA_URL_PREFIX = "data:image/svg+xml;charset=utf-8,"


@dataclass(frozen=True)
class LatexStyle:
    """The three knobs every LaTeX surface renders with.

    Frozen, so it can be handed to several viewmodels at once and compared by
    value: each of them keeps its own cache, and "did the style change?" is a
    question about the value rather than about which object holds it. ``0`` and
    ``""`` mean ziamath's own defaults (24 pt, bundled STIX Two Math); the
    settings store supplies real values.
    """

    color: str = "#000000"
    size: int = 24
    font: str = ""


def render_data_url(latex: str, style: LatexStyle) -> Tuple[str, int, int]:
    """Render ``latex`` for QML: ``(data URL, width, height)``.

    ``('', 0, 0)`` when ziamath cannot typeset it, which is the one contract every
    surface leans on — an empty URL is what makes a page fall back to plain text
    instead of showing a blank image.

    The URL is a data URL rather than a file because the artwork is per-entry and
    per-theme; the size comes back with it so the item can render at screen
    resolution (see `LatexImage`).
    """
    svg = latex_to_svg(
        latex,
        size=style.size or None,
        color=style.color or None,
        font=style.font or None,
    )
    if not svg:
        return ("", 0, 0)
    width, height = svg_size(svg)
    return (_DATA_URL_PREFIX + quote(svg, safe=""), width, height)


def svg_size(svg: str) -> Tuple[int, int]:
    """Return the SVG's intrinsic (width, height) in pixels, or ``(0, 0)``.

    Used to render at screen resolution (sourceSize x devicePixelRatio) so the
    LaTeX stays crisp on high-DPI displays.
    """
    w = _SVG_WIDTH_RE.search(svg)
    h = _SVG_HEIGHT_RE.search(svg)
    if not w or not h:
        return (0, 0)
    return int(round(float(w.group(1)))), int(round(float(h.group(1))))
