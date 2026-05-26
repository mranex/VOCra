from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class PipelineProgressBar(QWidget):
    COLORS = {
        "pending": QColor("#5f6b7a"),
        "running": QColor("#ff9800"),
        "done": QColor("#4caf50"),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._labels = ["Extract", "Crop", "Draft OCR", "Segment", "Preprocess", "Final OCR"]
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
        painter.setRenderHint(QPainter.Antialiasing)

        margin_x = 28
        top = 24
        bottom_label = 60
        radius = 10
        width = max(1, self.width() - margin_x * 2)
        spacing = width / max(1, len(self._labels) - 1)

        centers = [QPointF(margin_x + spacing * index, top) for index in range(len(self._labels))]
        for index in range(len(centers) - 1):
            status = "done" if self._statuses[index] == "done" and self._statuses[index + 1] == "done" else "pending"
            if self._statuses[index] == "running" or self._statuses[index + 1] == "running":
                status = "running"
            painter.setPen(QPen(self.COLORS[status], 4))
            painter.drawLine(centers[index], centers[index + 1])

        for index, center in enumerate(centers):
            status = self._statuses[index]
            color = self.COLORS.get(status, self.COLORS["pending"])
            painter.setPen(QPen(color, 2))
            painter.setBrush(color)
            painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2))

            painter.setPen(Qt.GlobalColor.white)
            text_rect = QRectF(center.x() - 45, bottom_label - 10, 90, 22)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._labels[index])
