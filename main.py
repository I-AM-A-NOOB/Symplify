import sys
from types import NoneType

import sympy as sp
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    BodyLabel,
    CardWidget,
    CommandBar,
    FlowLayout,
    FluentIcon,
    InfoBar,
    MessageBoxBase,
    PushButton,
    RoundMenu,
    ScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
    TableWidget,
    TextEdit,
    Theme,
    TitleLabel,
    TransparentDropDownPushButton,
    TransparentPushButton,
    TransparentToolButton,
    setTheme,
)
from qframelesswindow import FramelessWindow, StandardTitleBar

from app.common.font import FontManager
from app.components.highlighter import RainbowParenthesesHighlighter
from app.components.keyboard import KeyboardPanel
from app.components.splitter import Splitter
from app.core.calculator import SymbolicCalculator
from app.view.variables_view import VariablesView

class HistoryCard(CardWidget):
    """完全重写的带正确换行的历史记录卡片控件"""

    def __init__(
        self,
        expression,
        result,
        input_font: QFont = None,
        result_font: QFont = None,
        parent=None,
    ):
        super().__init__()
        self.expression = expression
        self.result = result
        self.input_font = input_font
        self.result_font = result_font

        # 创建主布局
        main_layout = QVBoxLayout(self)
        # main_layout.setContentsMargins(12, 10, 12, 10)
        # main_layout.setSpacing(20)

        # 表达式标签，支持正确换行
        self.input_label = StrongBodyLabel(expression)
        self.input_label.setFont(self.input_font)
        self.input_label.setWordWrap(True)
        self.input_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.input_label.setContextMenuPolicy(Qt.NoContextMenu)
        self.input_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.input_label.setMinimumWidth(0)
        main_layout.addWidget(self.input_label)

        # 结果标签，支持正确换行
        result_text = str(result) if not isinstance(result, NoneType) else "无结果"
        self.result_label = BodyLabel(result_text)
        self.result_label.setFont(self.result_font)
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.result_label.setContextMenuPolicy(Qt.NoContextMenu)
        self.result_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.result_label.setMinimumWidth(0)
        main_layout.addWidget(self.result_label)

        # 添加拉伸以将内容推到顶部
        main_layout.addStretch(1)

    def contextMenuEvent(self, event):
        """右键显示上下文菜单"""
        menu = RoundMenu(parent=self)

        # 复制表达式操作
        copy_expr = Action(FluentIcon.COPY, "复制表达式")
        copy_expr.triggered.connect(lambda: self._copy_text(self.expression))
        menu.addAction(copy_expr)

        # 复制结果操作
        result_text = str(self.result) if not isinstance(self.result, NoneType) else ""
        copy_result = Action(FluentIcon.COPY, "复制结果")
        copy_result.triggered.connect(lambda: self._copy_text(result_text))
        menu.addAction(copy_result)

        # 在光标位置显示菜单
        menu.exec(event.globalPos())

    def _copy_text(self, text):
        """复制文本到剪贴板"""
        QApplication.clipboard().setText(text)


class LogMessageBox(MessageBoxBase):
    """日志显示对话框"""

    def __init__(self, content: str, log_font: QFont = None, parent=None):
        super().__init__(parent)
        self.titleLabel = TitleLabel("计算日志", self)

        self.log_area = TextEdit(self)
        self.log_area.setFont(log_font)
        self.log_area.setReadOnly(True)
        self.log_area.setPlainText(content)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.log_area)

        self.yesButton.setText("确定")
        self.cancelButton.hide()


class DocumentationPanel(QWidget):
    def __init__(self, monospace_font, parent=None):
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.doc_title = StrongBodyLabel("函数文档")
        layout.addWidget(self.doc_title)
        self.doc_content = TextEdit()
        self.doc_content.setReadOnly(True)
        self.doc_content.setPlainText("将光标放在函数上查看文档")
        self.doc_content.setFont(monospace_font)
        layout.addWidget(self.doc_content)

    def update_documentation(self, title, content):
        self.doc_title.setText(title)
        self.doc_content.setPlainText(content)

    def reset(self):
        self.doc_title.setText("函数文档")
        self.doc_content.setPlainText("将光标放在函数上查看文档")


class HistoryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 15, 20, 10)
        self.title_label = TitleLabel("计算历史")
        header_layout.addWidget(self.title_label)
        self.clear_history_btn = PushButton("清除历史", header_widget)
        header_layout.addWidget(self.clear_history_btn, alignment=Qt.AlignRight)
        layout.addWidget(header_widget)
        self.history_scroll = ScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.history_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_widget)
        self.history_layout.setContentsMargins(15, 10, 15, 15)
        self.history_layout.setSpacing(10)
        # 添加占位文本
        self.placeholder_label = BodyLabel("您的计算历史将显示于此")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_layout.addWidget(self.placeholder_label)
        self.history_layout.addStretch(1)
        self.history_scroll.setWidget(self.history_widget)
        self.history_scroll.setStyleSheet(
            "QScrollArea{background: transparent; border: none}"
        )
        layout.addWidget(self.history_scroll)

    # 新增辅助方法：判断是否已有历史记录（不计占位标签）
    def _has_history_cards(self):
        count = 0
        for i in range(self.history_layout.count()):
            widget = self.history_layout.itemAt(i).widget()
            if widget and widget != self.placeholder_label:
                count += 1
        return count > 0

    def add_history_card(self, card_widget):
        # 如果存在占位标签，则移除
        if self.placeholder_label:
            self.history_layout.removeWidget(self.placeholder_label)
            self.placeholder_label.deleteLater()
            self.placeholder_label = None
        self.history_layout.insertWidget(0, card_widget)

    def clear_history_items(self):
        for i in reversed(range(self.history_layout.count())):
            item = self.history_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        # 如果没有历史记录，则重新添加占位标签

        self.placeholder_label = BodyLabel("您的计算历史将显示于此")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_layout.insertWidget(0, self.placeholder_label)


class CalculatorUI(FramelessWindow):
    """主应用程序窗口"""

    def __init__(self):
        super().__init__()
        self.calculator = SymbolicCalculator()
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
        self.setWindowTitle("Symplify - SymPy代数计算器")
        self.setWindowIcon(QIcon())
        self.resize(1024, 768)
        self.setMinimumSize(640, 480)
        self.center()
        setTheme(Theme.AUTO)
        self.log_content = ""

        self.monospace_font = FontManager.create_monospace(12)
        self.bold_monospace_font = FontManager.create_monospace(12, bold=True)
        self.large_monospace_font = FontManager.create_monospace(14)
        self.serif_font = FontManager.create_serif(12)
        self.create_ui_components()
        self.connect_signals()

    def create_ui_components(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 32, 8, 8)
        self.setLayout(main_layout)
        self.titleBar.raise_()

        self.command_bar = CommandBar(self)
        main_layout.addWidget(self.command_bar, 0)

        self.splitter = Splitter(Qt.Horizontal)
        self.splitter.setContentsMargins(10, 10, 10, 10)
        self.splitter.setHandleWidth(10)
        main_layout.addWidget(self.splitter)

        self.create_left_panel()
        self.create_right_panel()

        # self.splitter.setSizes([400, 600])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

    def create_left_panel(self):
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        input_layout = QVBoxLayout()

        # 修改：使用TextEdit替换LineEdit
        self.input_field = TextEdit()
        self.input_field.setPlaceholderText(
            "输入表达式，例如：x^2 + 2*x + 1 或 y = sin(x)"
        )
        self.input_field.setFont(self.large_monospace_font)
        self.rainbow_highlighter = RainbowParenthesesHighlighter(
            self.input_field.document()
        )
        input_layout.addWidget(self.input_field)

        self.create_function_panel(input_layout)
        # 修改：使用封装后的文档面板
        self.create_documentation_panel(input_layout)
        self.create_operation_buttons()
        input_layout.addLayout(self.buttons_layout)

        left_layout.addLayout(input_layout)

        container = QWidget()
        container.setLayout(left_layout)
        self.splitter.addWidget(container)

    # 修改文档面板封装：不再在此构建控件，而是使用 DocumentationPanel 类
    def create_documentation_panel(self, parent_layout):
        self.documentation_panel = DocumentationPanel(self.monospace_font)
        parent_layout.addWidget(self.documentation_panel)

    # 修改：使用 HistoryPanel 封装右侧历史记录面板
    def create_right_panel(self):
        self.history_panel = HistoryPanel()
        self.splitter.addWidget(self.history_panel)

    def create_function_panel(self, parent_layout):
        self.function_panel = KeyboardPanel(self.input_field, self.serif_font)
        parent_layout.addWidget(self.function_panel)

    def create_operation_buttons(self):
        self.buttons_layout = FlowLayout()
        self.buttons_layout.setVerticalSpacing(10)
        self.buttons_layout.setHorizontalSpacing(10)

        self.calc_button = TransparentPushButton(text="计算")
        self.calc_button.setIcon(FluentIcon.SEND)

        self.vars_button = TransparentPushButton(text="变量")
        self.vars_button.setIcon(FluentIcon.LABEL)

        self.example_button = TransparentDropDownPushButton("示例", self)

        self.log_button = TransparentPushButton(text="日志")
        self.log_button.setIcon(FluentIcon.HISTORY)

        self.command_bar.addWidget(self.calc_button)
        self.command_bar.addWidget(self.vars_button)
        self.command_bar.addWidget(self.example_button)
        self.command_bar.addSeparator()
        self.command_bar.addWidget(self.log_button)

    def connect_signals(self):
        self.calc_button.clicked.connect(self.calculate)
        # 删除原来的 returnPressed 信号绑定
        # self.input_field.returnPressed.connect(self.calculate)
        # 修改：添加 Ctrl+Enter 快捷键触发计算
        calc_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.input_field)
        calc_shortcut.activated.connect(self.calculate)
        self.example_button.clicked.connect(self.show_examples)
        self.vars_button.clicked.connect(self.show_variables)
        self.log_button.clicked.connect(self.show_log)
        # 修改：绑定新封装的历史面板的清除按钮事件
        self.history_panel.clear_history_btn.clicked.connect(self.clear_history)
        self.input_field.cursorPositionChanged.connect(
            self.schedule_documentation_update
        )

        # 添加撤销和重做快捷键
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self.input_field)
        undo_shortcut.activated.connect(self.input_field.undo)

        redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self.input_field)
        redo_shortcut.activated.connect(self.input_field.redo)

    def calculate(self):
        # 修改：从TextEdit获取文本内容
        expr = self.input_field.toPlainText().strip()
        if not expr:
            return
        result = self.calculator.process_expression(expr)
        if result.is_success:
            self.add_history_card(expr, result)
            self.log_content += f"> {expr}\n{result}\n"
            self.input_field.selectAll()
        else:
            InfoBar.error(
                title="错误", content=str(result.content), parent=self, duration=2000
            )
            self.log_content += f"> {expr}\n错误: {result.content}\n"

    def add_history_card(self, expr, result):
        history_card = HistoryCard(
            expr, result, self.bold_monospace_font, self.monospace_font
        )
        # 设置历史记录控件为父级以确保正确的父级链导航
        history_card.setParent(self.history_panel.history_widget)
        self.history_panel.add_history_card(history_card)

    def load_history_to_input(self, expr):
        self.input_field.setText(expr)
        self.input_field.setFocus()

    def clear_history(self):
        self.calculator.history = []
        self.history_panel.clear_history_items()
        InfoBar.info(title="信息", content="计算历史已清除", parent=self, duration=2000)

    def show_examples(self):
        menu = RoundMenu("示例", self)

        examples = [
            ("基本计算", "2*x + 3*x - 5"),
            ("函数使用", "sin(pi/2) + cos(0)"),
            ("变量赋值", "x = 5"),
            ("使用变量", "x**2 + 2*x + 1"),
            ("增强赋值", "x += 1"),
        ]

        for title, expr in examples:
            action = Action(
                text=f"{title}: {expr}",
                triggered=lambda checked, e=expr: self.input_field.setText(e),
            )
            menu.addAction(action)

        menu.exec(
            self.example_button.mapToGlobal(self.example_button.rect().bottomLeft())
        )

    def show_variables(self):
        """显示变量对话框"""
        vars_box = VariablesView(self.calculator, self)
        vars_box.exec()

    def show_log(self):
        log_box = LogMessageBox(self.log_content, self.monospace_font, self)
        log_box.exec()

    def center(self):
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def schedule_documentation_update(self):
        QTimer.singleShot(100, self.update_documentation)

    def update_documentation(self):
        if not self.input_field.hasFocus():
            return

        cursor_pos = self.input_field.textCursor().position()
        text = self.input_field.toPlainText()

        func_name = self.extract_function_name(text, cursor_pos)

        if func_name and hasattr(sp, func_name):
            func = getattr(sp, func_name)
            if callable(func):
                doc = func.__doc__
                if doc:
                    self.documentation_panel.update_documentation(
                        f"{func_name} 文档", doc
                    )
                    return

        self.documentation_panel.reset()

    def extract_function_name(self, text, cursor_pos):
        start = cursor_pos
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1

        end = cursor_pos
        while end < len(text) and (text[end].isalnum() or text[end] == "_"):
            end += 1

        if start < end:
            return text[start:end]
        return None


if __name__ == "__main__":
    app = QApplication(sys.argv)

    calculator = CalculatorUI()
    calculator.show()

    sys.exit(app.exec())
