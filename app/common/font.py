# coding=utf-8
from PySide6.QtGui import QFont


class FontManager:
    """字体管理类"""

    # 字体族常量
    MONOSPACE_FAMILIES = ["Consolas", "Microsoft YaHei", "Courier New", "Monospace"]
    SERIF_FAMILIES = ["Times New Roman", "NSimsun", "Courier New", "Serif"]

    @staticmethod
    def get_monospace(size:int=12, bold:bool=False)->QFont:
        """创建等宽字体"""
        font = QFont()
        font.setFamilies(FontManager.MONOSPACE_FAMILIES)
        font.setPointSize(size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        if bold:
            font.setWeight(QFont.Weight.Bold)
        return font

    @staticmethod
    def get_serif(size:int=12, bold:bool=False)->QFont:
        """创建衬线字体"""
        font = QFont()
        font.setFamilies(FontManager.SERIF_FAMILIES)
        font.setPointSize(size)
        font.setStyleHint(QFont.StyleHint.Serif)
        if bold:
            font.setWeight(QFont.Weight.Bold)
        return font
