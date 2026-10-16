from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qmlmathplot import MathPlotWidget

app = QApplication([])
window = QWidget()
box = QVBoxLayout(window)
plot = MathPlotWidget("sin(1/x)")  # drag to pan / wheel zooms anchored at the cursor
box.addWidget(plot)
window.show()
app.exec()
