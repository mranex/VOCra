from __future__ import annotations

from pathlib import Path

import cv2
from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class VideoPreview(QWidget):
    video_loaded = Signal(str)
    paused_changed = Signal(bool)
    video_size_changed = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.display_frame = QFrame(self)
        self.display_frame.setObjectName("VideoCard")
        display_layout = QVBoxLayout(self.display_frame)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(0)

        self.video_widget = QLabel(self.display_frame)
        self.video_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_widget.setMinimumSize(720, 405)
        self.video_widget.setText("Load a video to preview")
        display_layout.addWidget(self.video_widget)

        self.play_button = QPushButton("Play")
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setProperty("muted", True)

        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.seek_slider, 1)
        controls.addWidget(self.time_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.display_frame, 1)
        layout.addLayout(controls)

        self._source_path = ""
        self._video_width = 0
        self._video_height = 0
        self._fps = 25.0
        self._frame_count = 0
        self._duration_ms = 0
        self._position_ms = 0
        self._paused = True
        self._current_frame: QImage | None = None
        self._capture = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)

        self.play_button.clicked.connect(self.toggle_playback)
        self.seek_slider.sliderMoved.connect(self.seek_to)

    def set_source(self, video_path: str) -> None:
        self.close_source()

        self._source_path = str(Path(video_path).expanduser().resolve())
        self._capture = self._open_capture(self._source_path)
        if self._capture is None or not self._capture.isOpened():
            self.video_widget.setText("Failed to open video")
            return

        self._video_width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self._video_height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self._fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 25.0) or 25.0
        self._frame_count = int(self._capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._duration_ms = int((self._frame_count / self._fps) * 1000) if self._frame_count > 0 else 0
        self.seek_slider.setRange(0, max(0, self._duration_ms))
        self.video_size_changed.emit(self._video_width, self._video_height)

        self.seek_to(0)
        self._timer.stop()
        self._set_paused(True)
        self.video_loaded.emit(self._source_path)

    def source_path(self) -> str:
        return self._source_path

    def is_paused(self) -> bool:
        return self._paused

    def current_position_ms(self) -> int:
        return int(self._position_ms)

    def video_size(self) -> tuple[int, int]:
        return self._video_width, self._video_height

    def toggle_playback(self) -> None:
        if self._capture is None:
            return
        if self._paused:
            self._set_paused(False)
            self._timer.start(max(15, int(1000 / max(self._fps, 1.0))))
        else:
            self._set_paused(True)
            self._timer.stop()

    def capture_current_frame(self) -> QImage | None:
        return self._current_frame.copy() if self._current_frame is not None else None

    def seek_to(self, position_ms: int) -> None:
        if self._capture is None or not self._capture.isOpened():
            return
        target_ms = max(0, int(position_ms))
        target_frame = int((target_ms / 1000.0) * self._fps)
        target_frame = max(0, min(target_frame, max(0, self._frame_count - 1)))
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ok, frame = self._capture.read()
        if not ok or frame is None:
            return
        self._position_ms = int((target_frame / max(self._fps, 1.0)) * 1000)
        self._update_frame(frame)
        with QSignalBlocker(self.seek_slider):
            self.seek_slider.setValue(self._position_ms)
        self._update_time_label()

    def close_source(self) -> None:
        self._timer.stop()
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._source_path = ""
        self._current_frame = None
        self._position_ms = 0
        self._frame_count = 0
        self._duration_ms = 0
        self.seek_slider.setRange(0, 0)
        self._update_time_label()
        self._set_paused(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _advance_frame(self) -> None:
        if self._capture is None or self._paused:
            return
        ok, frame = self._capture.read()
        if not ok or frame is None:
            self._timer.stop()
            self._set_paused(True)
            return

        current_frame_index = int(self._capture.get(cv2.CAP_PROP_POS_FRAMES) or 0)
        self._position_ms = int((max(0, current_frame_index - 1) / max(self._fps, 1.0)) * 1000)
        with QSignalBlocker(self.seek_slider):
            self.seek_slider.setValue(self._position_ms)
        self._update_time_label()
        self._update_frame(frame)

    def _update_frame(self, frame) -> None:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, _channels = frame_rgb.shape
        bytes_per_line = frame_rgb.strides[0]
        self._current_frame = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).copy()
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._current_frame is None:
            return
        pixmap = QPixmap.fromImage(self._current_frame)
        scaled = pixmap.scaled(
            self.video_widget.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_widget.setPixmap(scaled)

    def _set_paused(self, paused: bool) -> None:
        self._paused = paused
        self.play_button.setText("Play" if paused else "Pause")
        self.paused_changed.emit(paused)

    def _update_time_label(self) -> None:
        self.time_label.setText(f"{_format_ms(self._position_ms)} / {_format_ms(self._duration_ms)}")

    def _open_capture(self, path: str):
        params = []
        if hasattr(cv2, "CAP_PROP_HW_ACCELERATION") and hasattr(cv2, "VIDEO_ACCELERATION_NONE"):
            params = [cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_NONE]
        capture = cv2.VideoCapture(path, cv2.CAP_FFMPEG, params)
        if capture.isOpened():
            return capture
        fallback = cv2.VideoCapture(path)
        return fallback


def _format_ms(value: int) -> str:
    total_seconds = max(0, int(value // 1000))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
