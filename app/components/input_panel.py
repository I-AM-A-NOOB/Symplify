from typing import Dict, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import PlainTextEdit, setCustomStyleSheet

from ..widgets.rainbow_brackets import RainbowBracketsHighlighter

BRACKETS: Dict[str, str] = {
    "(": ")",
    "[": "]",
    "{": "}",
}

COLORS: List[str] = [
    "#ff6b6b",
    "#ff9f43",
    "#ffd93d",
    "#6bcB77",
    "#4d96ff",
    "#9b5de5",
]


class InputPanel(QWidget):
    """输入面板组件，包含文本输入框和括号高亮功能"""

    # 定义信号
    calculate_requested = Signal()  # 请求计算信号

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        初始化输入面板

        Args:
            parent: 父级组件
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 输入框
        self.input_field = PlainTextEdit()
        self.cursor: QTextCursor = self.input_field.textCursor()
        layout.addWidget(self.input_field)

        # 默认高亮器
        self.highlighter = RainbowBracketsHighlighter(
            self.input_field.document(), BRACKETS, COLORS
        )

        # 设置快捷键
        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        """设置快捷键"""
        # 添加 Ctrl+Enter 快捷键触发计算
        calc_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.input_field)
        calc_shortcut.activated.connect(self._on_calculate_requested)

        # 添加撤销和重做快捷键
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self.input_field)
        undo_shortcut.activated.connect(self.input_field.undo)

        redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self.input_field)
        redo_shortcut.activated.connect(self.input_field.redo)

    def _on_calculate_requested(self) -> None:
        """处理计算请求"""
        self.calculate_requested.emit()

    def get_input_field(self) -> PlainTextEdit:
        """
        获取输入框实例

        Returns:
            PlainTextEdit: 输入框实例
        """
        return self.input_field

    def set_text(self, text: str) -> None:
        """
        设置输入框文本

        Args:
            text: 要设置的文本
        """
        self.input_field.setPlainText(text)

    def get_text(self) -> str:
        """
        获取输入框文本

        Returns:
            str: 输入框中的文本
        """
        return self.input_field.toPlainText()

    def clear_text(self) -> None:
        """清空输入框文本"""
        self.input_field.clear()

    def set_focus(self) -> None:
        """设置焦点到输入框"""
        self.input_field.setFocus()

    def select_all(self) -> None:
        """全选输入框内容并将光标移到末尾"""
        self.input_field.selectAll()
        self.cursor.movePosition(QTextCursor.MoveOperation.End)

    def load_expression(self, expression: str) -> None:
        """
        加载表达式到输入框

        Args:
            expression: 表达式文本
        """
        self.set_text(expression)
        self.cursor.movePosition(QTextCursor.MoveOperation.End)
        self.set_focus()

    def apply_settings(
        self,
        placeholder_text: Optional[str] = None,
        font: Optional[QFont] = None,
        bracket_pairs: Optional[Dict[str, str]] = None,
        bracket_colors: Optional[List[str]] = None,
    ) -> None:
        """
        应用输入面板设置

        Args:
            placeholder_text: 占位符文本
            font: 字体设置
            bracket_pairs: 括号配对字典
            bracket_colors: 括号颜色列表
        """
        if placeholder_text:
            self.input_field.setPlaceholderText(None)
            self.input_field.setPlaceholderText(placeholder_text)
        if font:
            self.input_field.setFont(font)
            input_field_qss = f"qplaintextedit::placeholder {{ font-family: {font.family()}; font-size: {font.pointSize()}pt; }}"
            setCustomStyleSheet(self.input_field, input_field_qss, input_field_qss)
            self.input_field.update()

        # 检查是否需要更新括号高亮器
        pairs = bracket_pairs if bracket_pairs is not None else BRACKETS
        colors = bracket_colors if bracket_colors is not None else COLORS

        if bracket_colors is not None or bracket_pairs is not None:
            # 重新创建高亮器
            self.highlighter = RainbowBracketsHighlighter(
                self.input_field.document(), pairs, colors
            )
