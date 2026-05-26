from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect
from PySide6.QtWidgets import (
    QFileDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vocra_gui.widgets.crop_overlay import CropOverlay
from vocra_gui.widgets.video_preview import VideoPreview


class SetupScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._crop_values: tuple[int, int, int, int] | None = None
        self._crop_locked = False

        self.video_path_edit = QLineEdit()
        self.video_path_edit.setReadOnly(True)
        self.project_dir_edit = QLineEdit()
        self.project_dir_edit.setReadOnly(True)

        self.load_video_button = QPushButton("Load Video")
        self.browse_project_button = QPushButton("Browse Project Dir")
        self.lock_crop_button = QPushButton("Lock Crop")
        self.lock_crop_button.setEnabled(False)
        self.create_project_button = QPushButton("Create Project")

        button_row = QHBoxLayout()
        button_row.addWidget(self.load_video_button)
        button_row.addWidget(self.browse_project_button)
        button_row.addWidget(self.lock_crop_button)
        button_row.addStretch(1)

        self.video_preview = VideoPreview(self)
        self.video_preview.video_widget.installEventFilter(self)
        self.video_preview.display_frame.installEventFilter(self)

        self.overlay = CropOverlay(self.video_preview.video_widget)
        self.overlay.raise_()

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 5.0)
        self.interval_spin.setDecimals(1)
        self.interval_spin.setSingleStep(0.1)
        self.interval_spin.setValue(0.5)

        self.crop_label = QLabel("x=- y=- w=- h=-")
        self.crop_label.setProperty("muted", True)
        self.crop_status_label = QLabel("Crop status: draw a region while paused")
        self.crop_status_label.setProperty("muted", True)

        form_card = QFrame()
        form_card.setObjectName("Card")
        form_layout = QFormLayout(form_card)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.addRow("Video", self.video_path_edit)
        form_layout.addRow("Project Dir", self.project_dir_edit)
        form_layout.addRow("Frame Interval (sec)", self.interval_spin)
        form_layout.addRow("Crop Region", self.crop_label)
        form_layout.addRow("Crop State", self.crop_status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addLayout(button_row)
        layout.addWidget(self.video_preview, 1)
        layout.addWidget(form_card)
        layout.addWidget(self.create_project_button, 0)

        self.load_video_button.clicked.connect(self.choose_video)
        self.browse_project_button.clicked.connect(self.choose_project_dir)
        self.lock_crop_button.clicked.connect(self.toggle_crop_lock)
        self.create_project_button.clicked.connect(self.create_project)
        self.video_preview.video_loaded.connect(self._on_video_loaded)
        self.video_preview.paused_changed.connect(self._on_paused_changed)
        self.video_preview.video_size_changed.connect(self.overlay.set_video_size)
        self.overlay.crop_changed.connect(self._on_crop_changed)

    def eventFilter(self, watched, event) -> bool:
        if watched in (self.video_preview.video_widget, self.video_preview.display_frame):
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                self._sync_overlay_geometry()
        return super().eventFilter(watched, event)

    def choose_video(self) -> None:
        video_path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            str(Path.cwd()),
            "Video Files (*.mp4 *.mkv *.avi *.mov);;All Files (*.*)",
        )
        if not video_path:
            return
        self.video_path_edit.setText(video_path)
        self.video_preview.set_source(video_path)
        if not self.project_dir_edit.text():
            suggested_dir = Path(video_path).with_suffix("").name
            self.project_dir_edit.setText(str(Path.cwd() / "projects" / suggested_dir))
        self._reset_crop_state()

    def choose_project_dir(self) -> None:
        project_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Project Directory",
            self.project_dir_edit.text() or str(Path.cwd()),
        )
        if project_dir:
            self.project_dir_edit.setText(project_dir)

    def create_project(self) -> None:
        if not self.video_path_edit.text().strip():
            QMessageBox.warning(self, "Missing Video", "Please load a video first.")
            return
        if not self.project_dir_edit.text().strip():
            QMessageBox.warning(self, "Missing Project Dir", "Please choose a project directory.")
            return
        if self._crop_values is None:
            QMessageBox.warning(self, "Missing Crop", "Pause the video and drag a crop region first.")
            return
        if not self._crop_locked:
            QMessageBox.warning(self, "Crop Not Locked", "Please lock the crop region before creating the project.")
            return

        crop = {
            "x": self._crop_values[0],
            "y": self._crop_values[1],
            "width": self._crop_values[2],
            "height": self._crop_values[3],
        }
        self.main_window.create_project(
            video_path=self.video_path_edit.text().strip(),
            project_dir=self.project_dir_edit.text().strip(),
            subtitle_crop=crop,
            frame_interval=float(self.interval_spin.value()),
        )

    def refresh_from_project(self, project_dir: str | None, progress: dict | None) -> None:
        if not project_dir or not progress:
            return
        self.project_dir_edit.setText(project_dir)
        self.video_path_edit.setText(str(progress.get("video_path", "")))
        self.interval_spin.setValue(float(progress.get("frame_extract", {}).get("interval_sec", 0.5)))
        crop = progress.get("subtitle_crop", {})
        if crop:
            self._crop_values = (
                int(crop.get("x", 0)),
                int(crop.get("y", 0)),
                int(crop.get("width", 0)),
                int(crop.get("height", 0)),
            )
            self.crop_label.setText(
                f"x={self._crop_values[0]} y={self._crop_values[1]} w={self._crop_values[2]} h={self._crop_values[3]}"
            )
            self.overlay.set_actual_crop_rect(*self._crop_values)
            self._crop_locked = True
            self.overlay.set_locked(True)
            self.lock_crop_button.setEnabled(True)
            self.lock_crop_button.setText("Unlock Crop")
            self.crop_status_label.setText("Crop status: locked and ready")
        video_path = str(progress.get("video_path", "") or "")
        if video_path and Path(video_path).exists() and self.video_preview.source_path() != str(Path(video_path).resolve()):
            self.video_preview.set_source(video_path)

    def _on_video_loaded(self, _path: str) -> None:
        self._sync_overlay_geometry()

    def _on_paused_changed(self, paused: bool) -> None:
        self.overlay.set_active(paused and not self._crop_locked)
        if paused and not self._crop_locked:
            self.crop_status_label.setText("Crop status: drawing enabled")
        elif self._crop_locked:
            self.crop_status_label.setText("Crop status: locked and ready")
        else:
            self.crop_status_label.setText("Crop status: pause video to draw crop")
        self._sync_overlay_geometry()

    def _on_crop_changed(self, x: int, y: int, width: int, height: int) -> None:
        self._crop_values = (x, y, width, height)
        self._crop_locked = False
        self.overlay.set_actual_crop_rect(x, y, width, height)
        self.crop_label.setText(f"x={x} y={y} w={width} h={height}")
        self.crop_status_label.setText("Crop status: unlocked, press Lock Crop when ready")
        self.lock_crop_button.setEnabled(True)
        self.lock_crop_button.setText("Lock Crop")
        self.overlay.set_locked(False)

    def toggle_crop_lock(self) -> None:
        if self._crop_values is None:
            return
        self._crop_locked = not self._crop_locked
        self.overlay.set_locked(self._crop_locked)
        self.overlay.set_active(self.video_preview.is_paused() and not self._crop_locked)
        if self._crop_locked:
            self.lock_crop_button.setText("Unlock Crop")
            self.crop_status_label.setText("Crop status: locked and ready")
        else:
            self.lock_crop_button.setText("Lock Crop")
            self.crop_status_label.setText("Crop status: unlocked, pause and adjust if needed")

    def _reset_crop_state(self) -> None:
        self._crop_values = None
        self._crop_locked = False
        self.overlay.clear_crop()
        self.crop_label.setText("x=- y=- w=- h=-")
        self.crop_status_label.setText("Crop status: pause video to draw crop")
        self.lock_crop_button.setEnabled(False)
        self.lock_crop_button.setText("Lock Crop")

    def _sync_overlay_geometry(self) -> None:
        target = self.video_preview.video_widget.geometry()
        self.overlay.setGeometry(QRect(0, 0, target.width(), target.height()))
        self.overlay.raise_()
        if self._crop_values is not None:
            self.overlay.set_actual_crop_rect(*self._crop_values)
