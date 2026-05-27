from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vocra_core.cropper import crop_frames
from vocra_core.draft_ocr import run_draft_ocr
from vocra_core.frame_extractor import extract_frames
from vocra_core.preprocessor import preprocess_representatives
from vocra_core.run_final_ocr import run_final_ocr
from vocra_core.segmenter import build_segments
from vocra_core.ssim_filter import filter_frames_by_ssim
from vocra_gui.widgets.log_panel import LogPanel
from vocra_gui.widgets.progress_bar import PipelineProgressBar
from vocra_gui.workers import TaskWorker


class ProcessScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._worker: TaskWorker | None = None
        self._active_task = ""
        self._draft_images: list[str] = []
        self._final_images: list[str] = []

        self.pipeline_bar = PipelineProgressBar()
        self.prepare_button = QPushButton("Prepare")
        self.draft_button = QPushButton("Draft OCR")
        self.final_button = QPushButton("Final OCR")

        button_card = QFrame()
        button_card.setObjectName("Card")
        button_layout = QVBoxLayout(button_card)
        button_layout.setContentsMargins(16, 16, 16, 16)
        button_layout.setSpacing(10)
        button_layout.addWidget(self.prepare_button)
        button_layout.addWidget(self.draft_button)
        button_layout.addWidget(self.final_button)

        self.preview_image = QLabel("No preview")
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumSize(320, 180)
        self.preview_image.setObjectName("VideoCard")
        self.preview_text = QLabel("OCR text preview will appear here.")
        self.preview_text.setWordWrap(True)

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.addWidget(QLabel("Current Preview"))
        preview_layout.addWidget(self.preview_image)
        preview_layout.addWidget(self.preview_text)

        self.log_panel = LogPanel()
        log_card = QFrame()
        log_card.setObjectName("Card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_layout.addWidget(QLabel("Log Panel"))
        log_layout.addWidget(self.log_panel)

        top_row = QHBoxLayout()
        top_row.addWidget(button_card, 0)
        top_row.addWidget(preview_card, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(self.pipeline_bar)
        layout.addLayout(top_row)
        layout.addWidget(log_card, 1)

        self.prepare_button.clicked.connect(self.start_prepare)
        self.draft_button.clicked.connect(self.start_draft)
        self.final_button.clicked.connect(self.start_final)

    def refresh_from_project(self, project_dir: str | None, progress: dict | None) -> None:
        enabled = bool(project_dir and progress)
        self.prepare_button.setEnabled(enabled and self._worker is None)
        self.draft_button.setEnabled(enabled and self._worker is None)
        self.final_button.setEnabled(enabled and self._worker is None)
        self.pipeline_bar.set_statuses(self._statuses_from_progress(progress or {}))
        if not enabled:
            self._draft_images = []
            self._final_images = []
            self.preview_image.clear()
            self.preview_image.setText("No preview")
            self.preview_text.setText("OCR text preview will appear here.")
            self.log_panel.clear()

    def start_prepare(self) -> None:
        if not self.main_window.project_dir:
            return

        def task(callback):
            extract_frames(self.main_window.project_dir, callback=lambda c, t, m: callback(c, t, f"Extract: {m}"))
            crop_frames(self.main_window.project_dir, callback=lambda c, t, m: callback(c, t, f"Crop: {m}"))
            filter_frames_by_ssim(self.main_window.project_dir, callback=lambda c, t, m: callback(c, t, f"SSIM: {m}"))

        self._active_task = "prepare"
        self.log_panel.append_log("Starting Prepare pipeline...")
        self._start_worker(task)

    def start_draft(self) -> None:
        if not self.main_window.project_dir:
            return
        project_path = Path(self.main_window.project_dir)
        self._draft_images = [str(path) for path in sorted((project_path / "cache" / "cropped").glob("*.png"))]

        def task(callback):
            run_draft_ocr(self.main_window.project_dir, callback=lambda c, t, m: callback(c, t, f"Draft OCR: {m}"))
            build_segments(self.main_window.project_dir, callback=lambda c, t, m: callback(c, t, f"Segment: {m}"))
            preprocess_representatives(
                self.main_window.project_dir,
                callback=lambda c, t, m: callback(c, t, f"Preprocess: {m}"),
            )

        self._active_task = "draft"
        self.log_panel.append_log("Starting Draft OCR pipeline...")
        self._start_worker(task)

    def start_final(self) -> None:
        if not self.main_window.project_dir:
            return
        project_path = Path(self.main_window.project_dir)
        segments_path = project_path / "cache" / "segments.json"
        self._final_images = []
        if segments_path.exists():
            data = json.loads(segments_path.read_text(encoding="utf-8"))
            self._final_images = [
                str(project_path / "cache" / "preprocessed" / segment["represent_image"])
                for segment in data.get("segments", [])
            ]

        def task(callback):
            run_final_ocr(self.main_window.project_dir, callback=lambda c, t, m: callback(c, t, f"Final OCR: {m}"))

        self._active_task = "final"
        self.log_panel.append_log("Starting Final OCR...")
        self._start_worker(task)

    def _start_worker(self, task_fn) -> None:
        self.prepare_button.setEnabled(False)
        self.draft_button.setEnabled(False)
        self.final_button.setEnabled(False)
        self._worker = TaskWorker(task_fn, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self.log_panel.append_log)
        self._worker.finished_with_status.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int, message: str) -> None:
        self.preview_text.setText(message)
        if self._active_task == "draft" and 0 < current <= len(self._draft_images):
            self._set_preview_image(self._draft_images[current - 1])
        elif self._active_task == "final" and 0 < current <= len(self._final_images):
            self._set_preview_image(self._final_images[current - 1])
        self.pipeline_bar.set_statuses(self._statuses_from_progress(self.main_window.progress or {}, running_task=self._active_task))

    def _on_finished(self, success: bool, message: str) -> None:
        if success:
            self.log_panel.append_log("Task finished successfully.")
        else:
            self.log_panel.append_log(f"Task stopped: {message}")
        self._worker = None
        self._active_task = ""
        self.main_window.reload_current_project()

    def _set_preview_image(self, image_path: str) -> None:
        if not Path(image_path).exists():
            return
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            self.preview_image.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_image.setPixmap(scaled)

    def _statuses_from_progress(self, progress: dict, running_task: str = "") -> list[str]:
        status = progress.get("status", {})
        statuses = [
            "done" if status.get("frames_extracted") else "pending",
            "done" if status.get("cropped_done") else "pending",
            "done" if status.get("ssim_filtered") else "pending",
            "done" if status.get("ocr_origin_done") else "pending",
            "done" if status.get("segments_done") else "pending",
            "done" if status.get("preprocessed_done") else "pending",
            "done" if status.get("ocr_final_done") else "pending",
        ]
        if running_task == "prepare":
            if statuses[0] != "done":
                statuses[0] = "running"
            elif statuses[1] != "done":
                statuses[1] = "running"
            elif statuses[2] != "done":
                statuses[2] = "running"
        elif running_task == "draft":
            if statuses[3] != "done":
                statuses[3] = "running"
            elif statuses[4] != "done":
                statuses[4] = "running"
            elif statuses[5] != "done":
                statuses[5] = "running"
        elif running_task == "final" and statuses[6] != "done":
            statuses[6] = "running"
        return statuses
