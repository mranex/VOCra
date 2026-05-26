from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocra_core.project_manager import save_progress
from vocra_core.run_translator import run_translation
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

        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        for code, label in LANGUAGE_OPTIONS:
            self.source_combo.addItem(label, code)
            self.target_combo.addItem(label, code)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 5000)
        self.batch_spin.setValue(300)

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

        counts_card = QFrame()
        counts_card.setObjectName("Card")
        counts_layout = QVBoxLayout(counts_card)
        counts_layout.setContentsMargins(16, 16, 16, 16)
        counts_layout.addWidget(QLabel("Translation is optional"))
        counts_layout.addWidget(self.total_label)
        counts_layout.addWidget(self.done_label)
        counts_layout.addWidget(self.progress_bar)

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addStretch(1)

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
            return

        translator = progress.get("translator", {})
        self._set_combo_data(self.source_combo, translator.get("source_lang", "auto"))
        self._set_combo_data(self.target_combo, translator.get("target_lang", "vi"))
        self.batch_spin.setValue(int(translator.get("batch_size", 300) or 300))

        cache_dir = Path(project_dir) / "cache"
        total_segments = 0
        translated_count = 0
        segments_path = cache_dir / "segments.json"
        translation_path = cache_dir / "translation.json"
        if segments_path.exists():
            total_segments = len(json.loads(segments_path.read_text(encoding="utf-8")).get("segments", []))
        if translation_path.exists():
            translated_count = len(json.loads(translation_path.read_text(encoding="utf-8")).get("items", []))
        self.total_label.setText(f"Total segments: {total_segments}")
        self.done_label.setText(f"Translated: {translated_count} / {total_segments}")
        percent = int((translated_count / total_segments) * 100) if total_segments else 0
        self.progress_bar.setValue(percent)

    def start_translation(self) -> None:
        if not self.main_window.project_dir or not self.main_window.progress:
            return
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
