from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocra_core.project_manager import save_progress
from vocra_core.run_translator import build_translation_signature, run_translation, translation_payload_matches
from vocra_gui.widgets.log_panel import LogPanel
from vocra_gui.workers import TaskWorker


LANGUAGE_OPTIONS = [
    ("auto", "Auto"),
    ("ja", "Japanese"),
    ("zh", "Chinese"),
    ("ko", "Korean"),
    ("en", "English"),
    ("vi", "Vietnamese"),
]


class TranslatorScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._worker: TaskWorker | None = None
        self._loading_context = False

        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        for code, label in LANGUAGE_OPTIONS:
            self.source_combo.addItem(label, code)
            self.target_combo.addItem(label, code)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 5000)
        self.batch_spin.setValue(300)
        self.video_context_edit = QPlainTextEdit()
        self.video_context_edit.setPlaceholderText(
            "Basic video info saved with this project.\n"
            "Example: Chinese comedy video, fake bank robbery setup, two main characters keep bickering."
        )
        self.video_context_edit.setFixedHeight(110)
        self.video_context_hint = QLabel(
            "Saved with this project. Use it for genre, setting, relationships, running jokes, or terminology."
        )
        self.video_context_hint.setWordWrap(True)
        self._context_save_timer = QTimer(self)
        self._context_save_timer.setSingleShot(True)
        self._context_save_timer.setInterval(700)
        self._context_save_timer.timeout.connect(self._save_video_context_if_needed)
        self.video_context_edit.textChanged.connect(self._schedule_video_context_save)

        self.total_label = QLabel("Total segments: 0")
        self.done_label = QLabel("Translated: 0 / 0")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.start_button = QPushButton("Start Translation")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        control_card = QFrame()
        control_card.setObjectName("Card")
        form = QFormLayout(control_card)
        form.setContentsMargins(16, 16, 16, 16)
        form.addRow("Source", self.source_combo)
        form.addRow("Target", self.target_combo)
        form.addRow("Batch Size", self.batch_spin)
        form.addRow("Video Info", self.video_context_edit)
        form.addRow(self.video_context_hint)

        counts_card = QFrame()
        counts_card.setObjectName("Card")
        counts_layout = QVBoxLayout(counts_card)
        counts_layout.setContentsMargins(16, 16, 16, 16)
        counts_layout.addWidget(QLabel("Translation is optional"))
        counts_layout.addWidget(self.total_label)
        counts_layout.addWidget(self.done_label)
        counts_layout.addWidget(self.progress_bar)

        primary_actions = QHBoxLayout()
        primary_actions.setSpacing(10)
        primary_actions.addWidget(self.start_button)
        primary_actions.addWidget(self.stop_button)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch(1)
        button_row.addLayout(primary_actions)

        self.log_panel = LogPanel()
        log_card = QFrame()
        log_card.setObjectName("Card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_layout.addWidget(QLabel("Log Panel"))
        log_layout.addWidget(self.log_panel)

        top_row = QHBoxLayout()
        top_row.addWidget(control_card, 0)
        top_row.addWidget(counts_card, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addLayout(top_row)
        layout.addLayout(button_row)
        layout.addWidget(log_card, 1)

        self.start_button.clicked.connect(self.start_translation)
        self.stop_button.clicked.connect(self.stop_translation)

    def refresh_from_project(self, project_dir: str | None, progress: dict | None) -> None:
        enabled = bool(project_dir and progress and progress.get("status", {}).get("ocr_final_done"))
        self.start_button.setEnabled(enabled and self._worker is None)
        self.stop_button.setEnabled(self._worker is not None)
        if not project_dir or not progress:
            self.total_label.setText("Total segments: 0")
            self.done_label.setText("Translated: 0 / 0")
            self.progress_bar.setValue(0)
            self.video_context_edit.clear()
            self.log_panel.clear()
            return

        translator = progress.get("translator", {})
        self._set_combo_data(self.source_combo, translator.get("source_lang", "auto"))
        self._set_combo_data(self.target_combo, translator.get("target_lang", "vi"))
        self.batch_spin.setValue(int(translator.get("batch_size", 300) or 300))
        self._loading_context = True
        self.video_context_edit.setPlainText(str(progress.get("video_context", "") or ""))
        self._loading_context = False

        cache_dir = Path(project_dir) / "cache"
        total_segments = 0
        translated_count = 0
        stale_translation_cache = False
        segments_path = cache_dir / "segments.json"
        translation_path = cache_dir / "translation.json"
        if segments_path.exists():
            total_segments = len(json.loads(segments_path.read_text(encoding="utf-8")).get("segments", []))
        if translation_path.exists():
            payload = json.loads(translation_path.read_text(encoding="utf-8"))
            translated_count = len(payload.get("items", []))
            stale_translation_cache = not translation_payload_matches(payload, build_translation_signature(progress))
            if stale_translation_cache:
                translated_count = 0
        self.total_label.setText(f"Total segments: {total_segments}")
        if stale_translation_cache:
            self.done_label.setText(f"Translated: 0 / {total_segments} (prompt/config changed)")
        else:
            self.done_label.setText(f"Translated: {translated_count} / {total_segments}")
        percent = int((translated_count / total_segments) * 100) if total_segments else 0
        self.progress_bar.setValue(percent)

    def start_translation(self) -> None:
        if not self.main_window.project_dir or not self.main_window.progress:
            return
        self._save_video_context_if_needed()
        progress = self.main_window.progress
        progress["translator"]["enabled"] = True
        progress["translator"]["source_lang"] = self.source_combo.currentData()
        progress["translator"]["target_lang"] = self.target_combo.currentData()
        progress["translator"]["batch_size"] = int(self.batch_spin.value())
        save_progress(self.main_window.project_dir, progress)

        self.log_panel.append_log("Starting translation...")
        self._worker = TaskWorker(
            lambda callback: run_translation(self.main_window.project_dir, callback=callback),
            self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self.log_panel.append_log)
        self._worker.finished_with_status.connect(self._on_finished)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._worker.start()

    def stop_translation(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()
            self.log_panel.append_log("Cancellation requested.")

    def _on_progress(self, current: int, total: int, message: str) -> None:
        percent = int((current / total) * 100) if total else 0
        self.progress_bar.setValue(percent)
        self.done_label.setText(f"Progress: batch {current} / {total}")

    def _on_finished(self, success: bool, message: str) -> None:
        if success:
            self.log_panel.append_log("Translation finished.")
        else:
            self.log_panel.append_log(f"Translation stopped: {message}")
        self._worker = None
        self.main_window.reload_current_project()

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _schedule_video_context_save(self) -> None:
        if self._loading_context:
            return
        self._context_save_timer.start()

    def _save_video_context_if_needed(self) -> None:
        if not self.main_window.project_dir or not self.main_window.progress:
            return
        current_text = self.video_context_edit.toPlainText().strip()
        existing_text = str(self.main_window.progress.get("video_context", "") or "").strip()
        if current_text == existing_text:
            return
        self.main_window.progress["video_context"] = current_text
        save_progress(self.main_window.project_dir, self.main_window.progress)
