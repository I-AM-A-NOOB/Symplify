# coding=utf-8
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QVBoxLayout
from qfluentwidgets import Theme, setTheme
from qframelesswindow import FramelessWindow, StandardTitleBar

from app.core.calculator import SymbolicCalculator
from app.view.calculator_interface import CalculatorView


class CalculatorWindow(FramelessWindow):
    """专注于窗体和全局资源的类"""

    def __init__(self):
        super().__init__()
        # 初始化全局资源
        self.calculator = SymbolicCalculator()

        # 设置窗口样式
        self.setup_window_style()

        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 32, 8, 8)
        self.setLayout(main_layout)

        # 创建UI视图并传递全局资源
        self.calculator_view = CalculatorView(self.calculator)
        main_layout.addWidget(self.calculator_view)

    def setup_window_style(self):
        """封装窗体本身样式的代码"""
        # 设置标题栏
        title_bar = StandardTitleBar(self)
        title_bar.titleLabel.setStyleSheet(
            """
            QLabel{
                background: transparent;
                padding: 0 4px
            }
        """
        )
        self.setTitleBar(title_bar)

        # 设置窗口属性
        self.setWindowTitle("Symplify - SymPy代数计算器")
        self.titleBar.raise_()
        self.setWindowIcon(QIcon())
        self.resize(1024, 768)
        self.setMinimumSize(640, 480)

        # 设置窗口位置和主题
        self.center()
        setTheme(Theme.AUTO)

    def center(self):
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 创建并显示主窗口
    window = CalculatorWindow()
    window.show()
    # 执行应用程序主循环
    sys.exit(app.exec())
