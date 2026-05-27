from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class PipelineProgressBar(QWidget):
    COLORS = {
        "pending": QColor("#3d285c"),
        "running": QColor("#ff007f"),
        "done": QColor("#00f0ff"),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._labels = ["Extract", "Crop", "SSIM", "Draft OCR", "Segment", "Preprocess", "Final OCR"]
        self._statuses = ["pending"] * len(self._labels)
        self.setMinimumHeight(82)

    def set_step_status(self, step_index: int, status: str) -> None:
        if 0 <= step_index < len(self._statuses):
            self._statuses[step_index] = status
            self.update()

    def set_statuses(self, statuses: list[str]) -> None:
        self._statuses = list(statuses[: len(self._labels)]) + ["pending"] * max(0, len(self._labels) - len(statuses))
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin_x = 28
        top = 24
        bottom_label = 60
        radius = 10
        width = max(1, self.width() - margin_x * 2)
        spacing = width / max(1, len(self._labels) - 1)

        centers = [QPointF(margin_x + spacing * index, top) for index in range(len(self._labels))]
        
        # Draw connection lines
        for index in range(len(centers) - 1):
            status = "done" if self._statuses[index] == "done" and self._statuses[index + 1] == "done" else "pending"
            if self._statuses[index] == "running" or self._statuses[index + 1] == "running":
                status = "running"
            
            line_color = self.COLORS[status]
            line_width = 4 if status != "pending" else 2.5
            painter.setPen(QPen(line_color, line_width))
            painter.drawLine(centers[index], centers[index + 1])

        # Draw nodes and labels
        for index, center in enumerate(centers):
            status = self._statuses[index]
            color = self.COLORS.get(status, self.COLORS["pending"])
            
            # Glow effect for active running node
            if status == "running":
                painter.setPen(QPen(QColor(255, 0, 127, 60), 6))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(center.x() - radius - 3, center.y() - radius - 3, (radius + 3) * 2, (radius + 3) * 2))
            
            painter.setPen(QPen(color, 2))
            painter.setBrush(color)
            painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2))

            # Style label text color based on status
            if status == "done":
                painter.setPen(QColor("#00f0ff"))  # Bright cyan
            elif status == "running":
                painter.setPen(QColor("#ff007f"))  # Neon pink
            else:
                painter.setPen(QColor("#8c7aa6"))  # Muted lavender
                
            text_rect = QRectF(center.x() - 45, bottom_label - 10, 90, 22)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._labels[index])

