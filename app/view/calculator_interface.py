from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    Action,
    CommandBar,
    FlowLayout,
    FluentIcon,
    InfoBar,
    MessageBoxBase,
    RoundMenu,
    TextEdit,
    TitleLabel,
    TransparentDropDownPushButton,
    TransparentPushButton,
)

from ..common.font import FontManager
from ..components.document_panel import DocumentPanel
from ..components.history_panel import HistoryPanel
from ..components.input_panel import InputPanel
from ..components.keyboard_panel import KeyboardPanel
from ..core.calculator import Result, SymbolicCalculator
from ..widgets.splitter import Splitter
from .variables_interface import VariablesView


class LogMessageBox(MessageBoxBase):
    """日志显示对话框"""

    def __init__(
        self, content: str, log_font: QFont = QFont(), parent: Optional[QWidget] = None
    ) -> None:
        """
        初始化日志消息框

        Args:
            content: 日志内容
            log_font: 日志字体
            parent: 父级组件
        """
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


class CalculatorView(QWidget):
    """计算器主视图类，负责UI组件的组织和交互"""

    def __init__(
        self,
        calculator: SymbolicCalculator,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        初始化计算器视图

        Args:
            calculator: 符号计算器实例
            parent: 父级组件
        """
        super().__init__(parent)
        self.calculator = calculator
        self.log_content = ""

        # 初始化控制器

        # 获取所需字体
        self.monospace_font = FontManager.get_monospace()
        self.bold_monospace_font = FontManager.get_monospace(bold=True)
        self.large_monospace_font = FontManager.get_monospace(14)
        self.serif_font = FontManager.get_serif()

        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建命令栏
        self.command_bar = CommandBar(self)
        main_layout.addWidget(self.command_bar, 0)

        # 创建分割器
        self.splitter = Splitter(Qt.Orientation.Horizontal)
        self.splitter.setContentsMargins(10, 10, 10, 10)
        self.splitter.setHandleWidth(10)
        main_layout.addWidget(self.splitter)

        # 创建左侧面板及其内容
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        input_layout = QVBoxLayout()

        # 使用 InputPanel 替代原来的 TextEdit
        self.input_panel = InputPanel()
        input_layout.addWidget(self.input_panel)

        # 函数面板
        self.function_panel = KeyboardPanel()
        self.function_panel.set_input_field(self.input_panel.get_input_field())
        input_layout.addWidget(self.function_panel)

        # 文档面板
        self.documentation_panel = DocumentPanel()
        self.documentation_panel.bind_input_field(
            self.input_panel.get_input_field()
        )  # 绑定输入框
        input_layout.addWidget(self.documentation_panel)

        # 操作按钮
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

        input_layout.addLayout(self.buttons_layout)
        left_layout.addLayout(input_layout)

        # 创建左侧容器并添加到分割器
        left_container = QWidget()
        left_container.setLayout(left_layout)
        self.splitter.addWidget(left_container)

        # 创建右侧历史面板
        self.history_panel = HistoryPanel()
        self.splitter.addWidget(self.history_panel)

        # 设置分割器比例
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        # 连接信号和槽
        self.connect_signals()

        # 应用设置
        self.apply_settings()

    def connect_signals(self) -> None:
        """连接信号和槽"""
        # 连接信号
        self.calc_button.clicked.connect(self.calculate)

        # 连接输入面板的计算请求信号
        self.input_panel.calculate_requested.connect(self.calculate)

        self.example_button.clicked.connect(self.show_examples)
        self.vars_button.clicked.connect(self.show_variables)
        self.log_button.clicked.connect(self.show_log)

        # 绑定历史面板的清除按钮事件
        self.history_panel.clear_history_btn.clicked.connect(self.clear_history)

        # 绑定历史面板的加载到输入框信号
        self.history_panel.expression_load_requested.connect(
            self.input_panel.load_expression
        )

    def calculate(self) -> None:
        """执行计算操作"""
        # 从InputPanel获取文本内容
        expr = self.input_panel.get_text().strip()
        if not expr:
            return
        result: Result = self.calculator.process_expression(expr)
        if result.is_success:
            self.add_history_card(expr, result)
            self.log_content += f"> {expr}\n{result}\n"
            self.input_panel.select_all()
        else:
            InfoBar.error(
                title="错误", content=str(result.content), parent=self, duration=2000
            )
            self.log_content += f"> {expr}\n错误: {result.content}\n"

    def add_history_card(self, expr: str, result: Result) -> None:
        """
        添加历史记录卡片

        Args:
            expr: 表达式
            result: 计算结果
        """
        # 调用HistoryPanel的方法来创建并添加历史卡片
        self.history_panel.add_history(expr, result)

    def clear_history(self) -> None:
        """清除历史记录"""
        self.history_panel.clear_history_items()
        InfoBar.info(title="信息", content="计算历史已清除", parent=self, duration=2000)

    def show_examples(self) -> None:
        """显示示例菜单"""
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
                triggered=lambda checked, e=expr: self.input_panel.set_text(e),
            )
            menu.addAction(action)

        menu.exec(
            self.example_button.mapToGlobal(self.example_button.rect().bottomLeft())
        )

    def show_variables(self) -> None:
        """显示变量对话框"""
        vars_box = VariablesView(self.calculator, self)
        vars_box.exec()

    def show_log(self) -> None:
        """显示日志对话框"""
        log_box = LogMessageBox(self.log_content, self.monospace_font, self)
        log_box.exec()

    def apply_settings(self) -> None:
        """应用所有设置到子组件"""
        # 应用输入面板设置
        self.input_panel.apply_settings(
            placeholder_text="请输入表达式，按 Ctrl+Enter 计算",
            font=self.large_monospace_font,
        )

        # 应用键盘面板设置
        self.function_panel.apply_settings(font=self.serif_font)

        # 应用文档面板设置
        self.documentation_panel.apply_settings(content_font=self.monospace_font)

        # 应用历史面板设置
        self.history_panel.apply_settings(
            input_font=self.bold_monospace_font, result_font=self.monospace_font
        )
