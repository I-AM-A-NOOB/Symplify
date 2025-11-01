from typing import Any, Callable, List, Optional, Union

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QGridLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CardWidget,
    DropDownPushButton,
    Flyout,
    FlyoutAnimationType,
    FlyoutViewBase,
    PlainTextEdit,
    PushButton,
    ScrollArea,
    SegmentedWidget,
    TextEdit,
)

from ..common.keyboard_config import load_keyboard_config


class GridKeyboardFlyout(FlyoutViewBase):
    """自定义键盘Flyout视图，支持二维列表布局"""

    def __init__(
        self,
        items_2d: List[List[Optional[List[str]]]],
        insert_callback: Callable[[str], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        初始化网格键盘Flyout

        Args:
            items_2d: 二维列表，包含键盘项数据
            insert_callback: 插入文本的回调函数
            parent: 父级组件
        """
        super().__init__(parent)
        self.items_2d = items_2d
        self.insert_callback = insert_callback

        # 保存需要在Flyout关闭时恢复焦点的目标（通常为KeyboardPanel实例）
        self.focus_parent = parent

        self.gridLayout = QGridLayout(self)
        self.gridLayout.setSpacing(2)

        # 按照二维列表结构添加按钮
        for row_index, row in enumerate(items_2d):
            for col_index, item in enumerate(row):
                if item is not None:  # 跳过空项
                    btn = PushButton(item[1])
                    btn.clicked.connect(lambda _, f=item[0]: self._on_item_clicked(f))
                    self.gridLayout.addWidget(btn, row_index, col_index)

    def _on_item_clicked(self, text: str) -> None:
        """
        处理项目点击事件

        Args:
            text: 要插入的文本
        """
        self.insert_callback(text)
        # 关闭flyout（closeEvent 将负责恢复焦点）
        self.close()

    def _on_focus_out(self) -> None:
        """点击外部区域时关闭flyout"""
        self.close()

    def closeEvent(self, event) -> None:
        """
        在Flyout关闭时把焦点恢复到父面板

        Args:
            event: 关闭事件
        """
        try:
            if self.focus_parent is not None:
                self.focus_parent.setFocus()
        except Exception:
            pass
        super().closeEvent(event)

    def apply_settings(self, font: Optional[QFont] = None) -> None:
        """
        应用设置到Flyout中的按钮

        Args:
            font: 字体设置
        """
        if font:
            for i in range(self.gridLayout.count()):
                widget = self.gridLayout.itemAt(i).widget()
                if isinstance(widget, PushButton):
                    widget.setFont(font)


class KeyboardPanel(CardWidget):
    """软键盘面板控件，支持空区域和下拉按钮"""

    # 修改配置字典，添加对空区域和下拉按钮的支持
    KEYBOARD_CONFIG = load_keyboard_config()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        初始化键盘面板

        Args:
            parent: 父级组件
        """
        super().__init__(parent)
        self.input_field = None
        self.keyboard_font: Optional[QFont] = None
        self.keyboard_layout = QVBoxLayout(self)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # 创建一个水平滚动区域来包含function_pivot
        self.pivot_scroll_area = ScrollArea()
        self.pivot_scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.pivot_scroll_area.setWidgetResizable(True)
        self.pivot_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.pivot_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.keyboard_pivot = SegmentedWidget()
        self.keyboard_pivot.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.pivot_scroll_area.setWidget(self.keyboard_pivot)
        self.pivot_scroll_area.setStyleSheet(
            "QScrollArea{background: transparent; border: none}"
        )

        self.keyboard_stacked = QStackedWidget()

        # 使用统一创建所有函数页面的方法
        self.create_all_pages()

        self.keyboard_layout.addWidget(self.pivot_scroll_area)
        self.keyboard_layout.addWidget(self.keyboard_stacked)
        self.keyboard_stacked.setCurrentIndex(0)
        self.keyboard_pivot.setCurrentItem("basic")

    def set_input_field(self, input_field: PlainTextEdit) -> None:
        """
        设置输入框

        Args:
            input_field: 输入框实例
        """
        self.input_field = input_field

    def create_all_pages(self) -> None:
        """根据配置字典动态创建所有函数页面"""
        for route_key, config in self.KEYBOARD_CONFIG.items():
            grid = config["grid"]
            page_title = config["title"]
            self._create_single_page(grid, page_title, route_key)

    def _create_single_page(
        self, keyboard_grid: List[List[Any]], page_title: str, route_key: str
    ) -> QWidget:
        """
        通用函数页面创建方法，使用网格布局

        Args:
            keyboard_grid: 键盘网格配置
            page_title: 页面标题
            route_key: 路由键

        Returns:
            QWidget: 创建的页面组件
        """
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(2)  # 减小间距使界面更紧凑

        # 遍历二维列表，按行列添加按钮
        for row_index, row in enumerate(keyboard_grid):
            for column_index, item in enumerate(row):
                # 支持多种类型的配置项
                if item is None or (isinstance(item, tuple) and item[0] is None):
                    pass
                elif isinstance(item, dict):
                    # 添加普通按钮，点击时显示Flyout
                    btn = DropDownPushButton(text=item.get("text", ""))
                    btn.setSizePolicy(
                        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
                    )

                    if self.keyboard_font:
                        btn.setFont(self.keyboard_font)

                    # 连接按钮点击事件
                    btn.clicked.connect(
                        lambda _, b=btn, items=item.get("items", []): self._show_flyout(
                            b, items
                        )
                    )

                    layout.addWidget(btn, row_index, column_index)
                else:
                    # 普通按钮处理
                    if isinstance(item, str):
                        text, display = item, item
                    else:
                        text, display = item

                    btn = PushButton(display)
                    btn.setSizePolicy(
                        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
                    )

                    if self.keyboard_font:
                        btn.setFont(self.keyboard_font)

                    btn.clicked.connect(lambda checked, f=text: self.insert_text(f))
                    layout.addWidget(btn, row_index, column_index)

        self.keyboard_stacked.addWidget(widget)
        self.keyboard_pivot.addItem(
            routeKey=route_key,
            text=page_title,
            onClick=lambda: self.keyboard_stacked.setCurrentWidget(widget),
        )

        return widget

    def _show_flyout(
        self,
        target_button: DropDownPushButton,
        items_2d: List[List[Optional[List[str]]]],
    ) -> None:
        """
        显示Flyout菜单，支持二维列表布局

        Args:
            target_button: 目标按钮
            items_2d: 二维项列表
        """
        flyout_view = GridKeyboardFlyout(
            items_2d, self.insert_text, parent=self.input_field
        )
        # 应用当前字体设置
        flyout_view.apply_settings(self.keyboard_font)
        Flyout.make(
            flyout_view,
            target_button,
            self,
            aniType=FlyoutAnimationType.DROP_DOWN,
            isDeleteOnClose=True,
        )

    def insert_text(self, function_text: str) -> None:
        """
        插入文本到输入框

        Args:
            function_text: 要插入的文本
        """
        if not self.input_field:
            return

        cursor: QTextCursor = self.input_field.textCursor()
        # 处理退格键（Backspace）
        if function_text == "\u0008":
            cursor.deletePreviousChar()
        # 处理删除键（Delete）
        elif function_text == "\u007f":
            cursor.deleteChar()
        else:
            # 插入普通文本
            cursor.insertText(function_text)
            # 如果包含左括号，调整光标到括号内
            if "(" in function_text:
                offset: int = function_text.find("(") + 1
                # 移动光标为：当前插入文本长度 - offset个字符回退
                steps = len(function_text) - offset
                for _ in range(steps):
                    cursor.movePosition(QTextCursor.MoveOperation.Left)
                self.input_field.setTextCursor(cursor)
        self.input_field.setTextCursor(cursor)
        self.input_field.setFocus()

    def apply_settings(self, font: Optional[QFont] = None) -> None:
        """
        应用键盘面板设置

        Args:
            font: 字体设置
        """
        if font:
            self.keyboard_font = font
            # 更新所有按钮的字体
            for i in range(self.keyboard_stacked.count()):
                widget = self.keyboard_stacked.widget(i)
                for child in widget.findChildren(PushButton):
                    child.setFont(font)
                for child in widget.findChildren(DropDownPushButton):
                    child.setFont(font)
