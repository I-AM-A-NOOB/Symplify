from PySide6.QtCore import QByteArray
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QApplication, QSizePolicy
from ziamath.config import config as zconfig
from ziamath.zmath import Latex

# Qt's QSvgRenderer ignores <use> transforms, so ziamath's default SVG2
# output (symbol + use) renders blank/clipped. svg2=False embeds glyph
# paths directly, which Qt renders correctly.
zconfig.svg2 = False

TeX = Latex(
    f"limit_{{x \\to 0}} \\frac{{\\sin({{x}})}}{{x}} = 1",
)

svg = TeX.svg()
print(svg)


svg_bytes = QByteArray(svg.encode("utf-8"))
app = QApplication([])
svg_widget = QSvgWidget(svg)
svg_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
svg_widget.renderer().load(svg_bytes)
svg_widget.show()
app.exec()
