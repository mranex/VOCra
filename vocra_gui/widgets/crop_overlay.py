from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class CropOverlay(QWidget):
    crop_changed = Signal(int, int, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self._active = False
        self._dragging = False
        self._start = QPoint()
        self._current = QPoint()
        self._rect = QRect()
        self._actual_rect = QRect()
        self._video_width = 0
        self._video_height = 0
        self._locked = False
        self.hide()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._refresh_visibility()
        self.update()

    def set_video_size(self, width: int, height: int) -> None:
        self._video_width = int(width)
        self._video_height = int(height)
        self._sync_widget_rect_from_actual()
        self.update()

    def crop_rect(self) -> QRect:
        return QRect(self._rect)

    def has_crop(self) -> bool:
        return not self._actual_rect.isNull()

    def is_locked(self) -> bool:
        return self._locked

    def set_locked(self, locked: bool) -> None:
        self._locked = bool(locked)
        self._refresh_visibility()
        self.update()

    def set_actual_crop_rect(self, x: int, y: int, width: int, height: int) -> None:
        self._actual_rect = QRect(int(x), int(y), int(width), int(height))
        self._sync_widget_rect_from_actual()
        self._refresh_visibility()
        self.update()

    def clear_crop(self) -> None:
        self._dragging = False
        self._rect = QRect()
        self._actual_rect = QRect()
        self._locked = False
        self._refresh_visibility()
        self.update()

    def mousePressEvent(self, event) -> None:
        if not self._active or self._locked or event.button() != Qt.MouseButton.LeftButton:
            return
        if not self._display_rect().contains(event.position().toPoint()):
            return
        self._dragging = True
        self._start = event.position().toPoint()
        self._current = self._start
        self._rect = QRect(self._start, self._current).normalized()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if not self._active or self._locked or not self._dragging:
            return
        display_rect = self._display_rect()
        point = event.position().toPoint()
        point.setX(min(max(point.x(), display_rect.left()), display_rect.right()))
        point.setY(min(max(point.y(), display_rect.top()), display_rect.bottom()))
        self._current = point
        self._rect = QRect(self._start, self._current).normalized()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if not self._active or self._locked or event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = False
        self._rect = QRect(self._start, self._current).normalized()
        actual_rect = self._map_to_video(self._rect)
        if actual_rect.width() > 0 and actual_rect.height() > 0:
            self._actual_rect = QRect(actual_rect)
            self.crop_changed.emit(actual_rect.x(), actual_rect.y(), actual_rect.width(), actual_rect.height())
        self.update()

    def paintEvent(self, event) -> None:
        del event
        if not self.isVisible() or self._rect.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen_color = QColor("#4caf50") if self._locked else QColor("#ffd54f")
        pen_style = Qt.PenStyle.SolidLine if self._locked else Qt.PenStyle.DashLine
        fill_color = QColor(76, 175, 80, 40) if self._locked else QColor(255, 213, 79, 36)
        pen = QPen(pen_color, 2, pen_style)
        painter.setPen(pen)
        painter.setBrush(fill_color)
        painter.drawRect(self._rect)

    def _display_rect(self) -> QRect:
        if self._video_width <= 0 or self._video_height <= 0:
            return self.rect()
        widget_ratio = self.width() / max(1, self.height())
        video_ratio = self._video_width / max(1, self._video_height)
        if widget_ratio > video_ratio:
            display_height = self.height()
            display_width = int(display_height * video_ratio)
            x = (self.width() - display_width) // 2
            return QRect(x, 0, display_width, display_height)
        display_width = self.width()
        display_height = int(display_width / max(video_ratio, 1e-6))
        y = (self.height() - display_height) // 2
        return QRect(0, y, display_width, display_height)

    def _map_to_video(self, rect: QRect) -> QRect:
        display = self._display_rect()
        if display.width() <= 0 or display.height() <= 0 or self._video_width <= 0 or self._video_height <= 0:
            return QRect()
        clipped = rect.intersected(display)
        scale_x = self._video_width / display.width()
        scale_y = self._video_height / display.height()
        x = int((clipped.x() - display.x()) * scale_x)
        y = int((clipped.y() - display.y()) * scale_y)
        width = int(clipped.width() * scale_x)
        height = int(clipped.height() * scale_y)
        return QRect(x, y, width, height)

    def _map_from_video(self, rect: QRect) -> QRect:
        display = self._display_rect()
        if display.width() <= 0 or display.height() <= 0 or self._video_width <= 0 or self._video_height <= 0:
            return QRect()
        scale_x = display.width() / self._video_width
        scale_y = display.height() / self._video_height
        x = int(display.x() + rect.x() * scale_x)
        y = int(display.y() + rect.y() * scale_y)
        width = int(rect.width() * scale_x)
        height = int(rect.height() * scale_y)
        return QRect(x, y, width, height)

    def _sync_widget_rect_from_actual(self) -> None:
        if self._actual_rect.isNull():
            self._rect = QRect()
            return
        self._rect = self._map_from_video(self._actual_rect)

    def _refresh_visibility(self) -> None:
        self.setVisible(self._locked or self._active or not self._rect.isNull())
