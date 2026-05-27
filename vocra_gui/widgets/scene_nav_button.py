from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QStylePainter, QToolButton


class SceneNavButton(QToolButton):
    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(54)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(max(hint.width(), 150), max(hint.height(), 54))

    def paintEvent(self, event) -> None:
        painter = QStylePainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        path = self._banner_path(self.rect().adjusted(1, 1, -1, -1))

        if not self.isEnabled():
            fill = QBrush(QColor("#08080a"))
            border = QPen(QColor("#181822"), 1.25)
            text_color = QColor("#4d4d56")
            font_bold = False
            chevrons_color = None
        else:
            if self.isChecked():
                # Active: Backlit spaceship purple to deep cyan gradient fill with laser cyan border
                grad = QLinearGradient(0, 0, self.width(), 0)
                grad.setColorAt(0, QColor("#220e40")) # Spaceship purple
                grad.setColorAt(1, QColor("#03202e")) # Deep cyan
                fill = QBrush(grad)
                border = QPen(QColor("#00f0ff"), 1.75) # Glowing laser cyan
                text_color = QColor("#ffffff")
                font_bold = True
                chevrons_color = QColor("#00f0ff") # active cyan chevrons
            elif self.underMouse():
                # Hover: Brighter backlit gradient fill with glowing violet border
                grad = QLinearGradient(0, 0, self.width(), 0)
                grad.setColorAt(0, QColor("#361666")) # Brighter purple
                grad.setColorAt(1, QColor("#053c57")) # Brighter deep cyan
                fill = QBrush(grad)
                border = QPen(QColor("#a800ff"), 1.5) # Glowing violet
                text_color = QColor("#ffffff")
                font_bold = False
                chevrons_color = QColor("#a800ff") # hover purple chevrons
            else:
                # Default: Subtle backlit spaceship purple-cyan gradient fill with mecha purple border
                grad = QLinearGradient(0, 0, self.width(), 0)
                grad.setColorAt(0, QColor("#150a26")) # Subtle mecha purple
                grad.setColorAt(1, QColor("#09121c")) # Subtle deep slate cyan
                fill = QBrush(grad)
                border = QPen(QColor("#2d2440"), 1.25) # Purple mecha panel border
                text_color = QColor("#a39bb8") # Subtle silver-purple text
                font_bold = False
                chevrons_color = None

        painter.fillPath(path, fill)
        painter.setPen(border)
        painter.drawPath(path)

        # Draw decorative glowing chevron indicators (>>>) on the left side of active/hover buttons
        if chevrons_color:
            painter.setPen(QPen(chevrons_color, 1.75))
            start_x = 24
            mid_y = self.height() // 2
            size = 5
            for i in range(3):
                offset_x = start_x + (i * 7)
                painter.drawLine(offset_x - size, mid_y - size, offset_x, mid_y)
                painter.drawLine(offset_x, mid_y, offset_x - size, mid_y + size)

        font = self.font()
        font.setBold(font_bold)
        font.setPointSize(10.5 if font_bold else 10)
        painter.setFont(font)

        painter.setPen(text_color)
        text_rect = self.rect().adjusted(45, 0, -22, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.text())


    def _banner_path(self, rect: QRect) -> QPainterPath:
        width = max(48, rect.width())
        height = max(24, rect.height())
        tip = min(22, max(14, width // 7))
        left = rect.left()
        top = rect.top()
        right = rect.left() + width
        bottom = rect.top() + height
        mid_y = top + (height // 2)

        path = QPainterPath()
        # Start top-left
        path.moveTo(QPoint(left, top))
        # Top line
        path.lineTo(QPoint(right - tip, top))
        # Right pointy edge
        path.lineTo(QPoint(right, mid_y))
        # Bottom-right line
        path.lineTo(QPoint(right - tip, bottom))
        # Bottom line
        path.lineTo(QPoint(left, bottom))
        # Left indent edge
        path.lineTo(QPoint(left + tip, mid_y))
        path.closeSubpath()
        return path



