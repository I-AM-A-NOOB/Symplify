import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget


class RainbowParenthesesHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 定义彩虹颜色序列：赤、橙、黄、绿、青、蓝、紫
        self.colors = [
            QColor(255, 0, 0),  # 赤红
            QColor(255, 165, 0),  # 橙色
            QColor(255, 255, 0),  # 黄色
            QColor(0, 255, 0),  # 绿色
            QColor(0, 255, 255),  # 青色
            QColor(0, 0, 255),  # 蓝色
            QColor(255, 0, 255),  # 紫色
        ]
        # 未配对括号的颜色
        self.unmatched_color = QColor(128, 128, 128)  # 灰色

    def highlightBlock(self, text):
        if not text:
            return

        # 初始化当前块的括号层级状态
        current_block_level = 0
        # 获取前一个文本块的最终括号层级状态
        previous_block_state = self.previousBlockState()
        if previous_block_state != -1:
            current_block_level = previous_block_state

        # 存储括号格式事件
        parentheses = []
        # 记录左括号的栈，存放 (index, level)
        stack = []

        # 遍历当前文本块字符，记录括号类型和层级
        for index, char in enumerate(text):
            if char == "(":
                # 记录左括号
                parentheses.append((index, "open", current_block_level))
                stack.append((index, current_block_level))
                current_block_level += 1
            elif char == ")":
                if stack:
                    # 匹配栈顶的左括号
                    left_index, left_level = stack.pop()
                    current_block_level = left_level  # 与左括号对应的层级
                    parentheses.append((index, "close", left_level))
                else:
                    parentheses.append((index, "close_unmatched", 0))

        # 调整当前块的状态
        self.setCurrentBlockState(max(0, current_block_level))

        # 未匹配左括号集合
        unmatched_left = {item[0] for item in stack}

        # 应用高亮
        for index, p_type, level in parentheses:
            if p_type == "open":
                if index in unmatched_left:
                    self.setFormat(
                        index, 1, self.create_char_format(self.unmatched_color)
                    )
                else:
                    color_index = level % len(self.colors)
                    self.setFormat(
                        index, 1, self.create_char_format(self.colors[color_index])
                    )
            elif p_type == "close":
                color_index = level % len(self.colors)
                self.setFormat(
                    index, 1, self.create_char_format(self.colors[color_index])
                )
            else:  # close_unmatched
                self.setFormat(index, 1, self.create_char_format(self.unmatched_color))

    @staticmethod
    def create_char_format(color: QColor) -> QTextCharFormat:
        """创建文本字符格式"""
        char_format = QTextCharFormat()
        char_format.setForeground(color)  # 设置前景色（字体颜色）
        char_format.setFontWeight(700)  # 设置字体加粗，使括号更醒目
        return char_format


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.text_edit = QTextEdit()
        # 设置初始文本，包含一些嵌套括号和未配对括号用于测试
        self.text_edit.setPlainText("())(((())))(")
        layout.addWidget(self.text_edit)

        # 创建彩虹括号高亮器实例，并应用于QTextEdit的文档
        self.highlighter = RainbowParenthesesHighlighter(self.text_edit.document())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
