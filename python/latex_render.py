# coding: utf-8
"""LaTeX -> SVG rendering via ziamath.

Qt's QSvgRenderer ignores ``<use>`` transforms, so ziamath's default SVG2
output (symbol + use) renders blank/clipped. Setting ``svg2 = False``
embeds the glyph paths directly, which Qt renders correctly.
"""

import re
from typing import Optional, Tuple

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
