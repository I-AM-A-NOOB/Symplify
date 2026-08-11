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


def latex_to_svg(latex: str, size: Optional[float] = None) -> str:
    """Render a LaTeX string to an SVG string, or ``''`` if it cannot be parsed.

    Args:
        latex: The LaTeX source.
        size: Optional font size in points; the ziamath default (24) is used
            when None. Exposed so a settings option can drive it later.
    """
    try:
        from ziamath.zmath import Latex

        if size is None:
            return Latex(latex).svg()
        return Latex(latex, size=size).svg()
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
