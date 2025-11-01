from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QSplitter, QSplitterHandle


class SplitterHandle(QSplitterHandle):
    """自定义分割器的Handle类，带有胶囊形图标"""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.isHover = False

    def sizeHint(self):
        """重写sizeHint以确保handle有正确的尺寸(10px)"""
        if self.orientation() == Qt.Orientation.Horizontal:
            return QSize(10, super().sizeHint().height())
        elif self.orientation() == Qt.Orientation.Vertical:
            return QSize(super().sizeHint().width(), 10)
        else:
            return None

    def enterEvent(self, e):
        self.isHover = True
        self.update()

    def leaveEvent(self, e):
        self.isHover = False
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self.isHover:
            painter.setBrush(QBrush(QColor(191, 191, 191, 63)))
            painter.setPen(Qt.PenStyle.NoPen)
            background_rect = self.rect()
            painter.drawRect(background_rect)

        painter.setBrush(QBrush(QColor(127, 127, 127)))
        painter.setPen(Qt.PenStyle.NoPen)

        capsule_weigh = 4
        capsule_length = 30
        radius = 2

        if self.orientation() == Qt.Orientation.Horizontal:
            x = (self.width() - capsule_weigh) // 2
            y = (self.height() - capsule_length) // 2
            painter.drawRoundedRect(
                QRect(x, y, capsule_weigh, capsule_length), radius, radius
            )
        elif self.orientation() == Qt.Orientation.Vertical:
            x = (self.width() - capsule_length) // 2
            y = (self.height() - capsule_weigh) // 2
            painter.drawRoundedRect(
                QRect(x, y, capsule_length, capsule_weigh), radius, radius
            )


class Splitter(QSplitter):
    """自定义的QSplitter类"""

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)

    def createHandle(self):
        return SplitterHandle(self.orientation(), self)
