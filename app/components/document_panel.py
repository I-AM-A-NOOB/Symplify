import sympy as sp
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import StrongBodyLabel, TextEdit
from typing import Optional


class DocumentPanel(QWidget):
    """文档面板组件，用于显示函数文档"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        初始化文档面板
        
        Args:
            parent: 父级组件
        """
        super().__init__(parent)
        self.input_field = None
        # 添加缓存以避免重复计算
        self._last_cursor_pos: int = -1
        self._last_text_hash: int = -1
        self._current_func_name: Optional[str] = None

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.doc_title = StrongBodyLabel("函数文档")
        layout.addWidget(self.doc_title)
        self.doc_content = TextEdit()
        self.doc_content.setReadOnly(True)
        self.doc_content.setPlainText("将光标放在函数上查看文档")
        layout.addWidget(self.doc_content)

    def bind_input_field(self, input_field) -> None:
        """
        绑定输入框并设置文档更新逻辑
        
        Args:
            input_field: 输入框实例
        """
        self.input_field = input_field
        if self.input_field:
            self.input_field.cursorPositionChanged.connect(
                self.schedule_documentation_update
            )

    def schedule_documentation_update(self) -> None:
        """延迟更新文档，避免频繁更新"""
        QTimer.singleShot(100, self._auto_update_documentation)

    def _auto_update_documentation(self) -> None:
        """根据光标位置自动更新文档（内部方法）"""
        if not self.input_field or not self.input_field.hasFocus():
            return

        cursor_pos = self.input_field.textCursor().position()
        text = self.input_field.toPlainText()
        text_hash = hash(text)

        # 如果光标位置和文本内容都没有变化，则不更新
        if cursor_pos == self._last_cursor_pos and text_hash == self._last_text_hash:
            return

        # 更新缓存
        self._last_cursor_pos = cursor_pos
        self._last_text_hash = text_hash

        # 如果文本为空，直接重置文档面板
        if not text.strip():
            self.reset()
            return

        func_name = self.extract_function_name(text, cursor_pos)

        # 如果函数名没有变化，则不更新
        if func_name == self._current_func_name:
            return

        self._current_func_name = func_name

        if func_name and hasattr(sp, func_name):
            func = getattr(sp, func_name)
            if callable(func):
                doc = func.__doc__
                if doc:
                    self._update_doc_panel(f"{func_name} 文档", doc)
                    return

        self.reset()

    def extract_function_name(self, text: str, cursor_pos: int) -> Optional[str]:
        """
        从文本中提取光标位置的函数名
        
        Args:
            text: 输入的文本
            cursor_pos: 光标位置
            
        Returns:
            str or None: 提取到的函数名，如果没有则返回None
        """
        start = cursor_pos
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1

        end = cursor_pos
        while end < len(text) and (text[end].isalnum() or text[end] == "_"):
            end += 1

        if start < end:
            return text[start:end]
        return None

    def _update_doc_panel(self, title: str, content: str) -> None:
        """
        更新文档面板显示
        
        Args:
            title: 文档标题
            content: 文档内容
        """
        self.doc_title.setText(title)
        self.doc_content.setPlainText(content)

    def update_documentation(self, title: str, content: str) -> None:
        """
        供外部调用的更新文档方法，保持向后兼容
        
        Args:
            title: 文档标题
            content: 文档内容
        """
        self._update_doc_panel(title, content)

    def reset(self) -> None:
        """重置文档面板显示"""
        # 只有在当前不是默认状态时才重置
        if self._current_func_name is not None:
            self._current_func_name = None
            self.doc_title.setText("函数文档")
            self.doc_content.setPlainText("将光标放在函数上查看文档")
        
    def apply_settings(self, content_font: Optional[QFont] = None) -> None:
        """
        应用文档面板设置
        
        Args:
            content_font: 内容字体
        """
        if content_font:
            self.doc_content.setFont(content_font)