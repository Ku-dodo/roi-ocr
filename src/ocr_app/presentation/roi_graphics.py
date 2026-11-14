from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsSimpleTextItem


class RoiOutline(QGraphicsRectItem):
    def boundingRect(self):
        return super().boundingRect().adjusted(-1, -1, 1, 1)

    def paint(self, painter, option, widget=None):
        """확대율과 무관한 검은 외곽선 위에 ROI 색상 선을 그려 대비를 확보한다."""
        painter.setBrush(Qt.BrushStyle.NoBrush)
        outline = QPen(QColor("#10151d"), 4)
        outline.setCosmetic(True)
        painter.setPen(outline)
        painter.drawRect(self.rect())
        painter.setPen(self.pen())
        painter.drawRect(self.rect())


class RoiTagBadge(QGraphicsSimpleTextItem):
    def __init__(self, color: QColor, parent):
        super().__init__(parent)
        self._color = color
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.setFont(font)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self):
        return super().boundingRect().adjusted(0, 0, 24, 8)

    def paint(self, painter, option, widget=None):
        """짙은 배경·흰 Tag·ROI 색상 표식을 화면 크기가 일정한 배지로 그린다."""
        rect = self.boundingRect()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#5a6575"), 1))
        painter.setBrush(QColor(16, 21, 29, 235))
        painter.drawRoundedRect(rect.adjusted(.5, .5, -.5, -.5), 4, 4)
        painter.fillRect(QRectF(6, 6, 5, rect.height() - 12), self._color)
        painter.setFont(self.font())
        painter.setPen(QColor("#ffffff"))
        painter.drawText(rect.adjusted(17, 4, -7, -4), Qt.AlignmentFlag.AlignVCenter, self.text())
