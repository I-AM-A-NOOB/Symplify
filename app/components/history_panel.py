from types import NoneType
from typing import Any, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    BodyLabel,
    CardWidget,
    FluentIcon,
    PushButton,
    RoundMenu,
    ScrollArea,
    StrongBodyLabel,
    TitleLabel,
)


class HistoryCard(CardWidget):
    """完全重写的带正确换行的历史记录卡片控件"""

    # 添加信号，当用户选择将表达式加载到输入框时发出
    load_to_input = Signal(str)

    def __init__(
        self,
        expression: str,
        result: Any,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        初始化历史记录卡片

        Args:
            expression: 表达式文本
            result: 计算结果
            parent: 父级组件
        """
        super().__init__(parent)
        self.expression = expression
        self.result = result
        self.input_font = QFont()
        self.result_font = QFont()

        # 创建主布局
        main_layout = QVBoxLayout(self)
        # main_layout.setContentsMargins(12, 10, 12, 10)
        # main_layout.setSpacing(20)

        # 表达式标签，支持正确换行
        self.input_label = StrongBodyLabel(expression)
        self.input_label.setFont(self.input_font)
        self.input_label.setWordWrap(True)
        self.input_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.input_label.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
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
        self.result_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.result_label.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.result_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.result_label.setMinimumWidth(0)
        main_layout.addWidget(self.result_label)

        # 添加拉伸以将内容推到顶部
        main_layout.addStretch(1)

    def contextMenuEvent(self, event) -> None:
        """
        右键显示上下文菜单

        Args:
            event: 上下文菜单事件
        """
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

        # 加载到输入框操作
        load_expr = Action(FluentIcon.EDIT, "加载到输入框")
        load_expr.triggered.connect(lambda: self.load_to_input.emit(self.expression))
        menu.addAction(load_expr)

        # 在光标位置显示菜单
        menu.exec(event.globalPos())

    def _copy_text(self, text: str) -> None:
        """
        复制文本到剪贴板

        Args:
            text: 要复制的文本
        """
        QApplication.clipboard().setText(text)

    def apply_settings(
        self, input_font: Optional[QFont] = None, result_font: Optional[QFont] = None
    ) -> None:
        """
        应用历史卡片设置

        Args:
            input_font: 输入字体
            result_font: 结果字体
        """
        if input_font:
            self.input_font = input_font
            self.input_label.setFont(input_font)

        if result_font:
            self.result_font = result_font
            self.result_label.setFont(result_font)


class HistoryPanel(QWidget):
    """历史记录面板，用于显示计算历史"""

    # 添加信号，当用户选择将表达式加载到输入框时传递给父组件
    expression_load_requested = Signal(str)

    # 限制历史记录数量以防止内存问题
    MAX_HISTORY_ITEMS = 100

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        初始化历史记录面板

        Args:
            parent: 父级组件
        """
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
        header_layout.addWidget(
            self.clear_history_btn, alignment=Qt.AlignmentFlag.AlignRight
        )
        layout.addWidget(header_widget)
        self.history_scroll = ScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.history_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
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

        # 存储当前设置的字体
        self.current_input_font: Optional[QFont] = None
        self.current_result_font: Optional[QFont] = None

    # 新增辅助方法：判断是否已有历史记录（不计占位标签）
    def _has_history_cards(self) -> bool:
        """
        判断是否已有历史记录（不计占位标签）

        Returns:
            bool: 如果有历史记录返回True，否则返回False
        """
        count = 0
        for i in range(self.history_layout.count()):
            widget = self.history_layout.itemAt(i).widget()
            if widget and widget != self.placeholder_label:
                count += 1
        return count > 0

    def insert_history_card(self, card_widget: HistoryCard) -> None:
        """
        插入历史记录卡片

        Args:
            card_widget: 历史卡片组件
        """
        # 如果存在占位标签，则移除
        if self.placeholder_label:
            self.history_layout.removeWidget(self.placeholder_label)
            self.placeholder_label.deleteLater()
            self.placeholder_label = None

        # 在开头插入新卡片
        self.history_layout.insertWidget(0, card_widget)

        # 限制历史记录数量以防止内存问题
        self._trim_history_if_needed()

    def _trim_history_if_needed(self) -> None:
        """如果历史记录过多，则删除最旧的记录"""
        # 计算历史卡片数量（排除占位符）
        history_count = 0
        history_widgets: List[QWidget] = []
        for i in range(self.history_layout.count()):
            widget = self.history_layout.itemAt(i).widget()
            if widget and widget != self.placeholder_label:
                history_count += 1
                history_widgets.append(widget)

        # 如果超过最大数量，删除最旧的记录
        if history_count > self.MAX_HISTORY_ITEMS:
            # 从末尾开始删除多余的卡片
            for i in range(len(history_widgets) - 1, self.MAX_HISTORY_ITEMS - 1, -1):
                widget = history_widgets[i]
                self.history_layout.removeWidget(widget)
                widget.deleteLater()

    def clear_history_items(self) -> None:
        """清空历史记录项"""
        for i in reversed(range(self.history_layout.count())):
            item = self.history_layout.itemAt(i)
            if item.widget() and item.widget() != self.placeholder_label:
                item.widget().deleteLater()
        # 如果没有历史记录，则重新添加占位标签

        self.placeholder_label = BodyLabel("您的计算历史将显示于此")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_layout.insertWidget(0, self.placeholder_label)

    def add_history(self, expression: str, result: Any) -> None:
        """
        创建并添加历史记录卡片到面板

        Args:
            expression: 表达式文本
            result: 计算结果
        """
        # 创建历史卡片
        history_card = HistoryCard(expression, result)
        # 应用当前设置的字体
        history_card.apply_settings(self.current_input_font, self.current_result_font)
        # 设置此面板的widget为父级以确保正确的父级链导航
        history_card.setParent(self.history_widget)
        # 连接信号，当用户选择加载到输入框时传递给父组件
        history_card.load_to_input.connect(self.expression_load_requested.emit)
        # 添加到布局中
        self.insert_history_card(history_card)

    def apply_settings(
        self, input_font: Optional[QFont] = None, result_font: Optional[QFont] = None
    ) -> None:
        """
        应用历史面板设置

        Args:
            input_font: 输入字体
            result_font: 结果字体
        """
        # 保存当前字体设置
        if input_font is not None:
            self.current_input_font = input_font
        if result_font is not None:
            self.current_result_font = result_font

        # 对于已存在的历史卡片，应用设置
        for i in range(self.history_layout.count()):
            widget = self.history_layout.itemAt(i).widget()
            if widget and hasattr(widget, "apply_settings"):
                widget.apply_settings(input_font, result_font)
