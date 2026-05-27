from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QSplitter,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocra_translator.core.translation_service import run_project_translation
from vocra_translator.widgets.log_panel import LogPanel
from vocra_translator.widgets.subtitle_table import SubtitleTable
from vocra_translator.widgets.task_worker import TaskWorker


LANGUAGE_OPTIONS = [
    ("auto", "Auto"),
    ("ja", "Japanese"),
    ("zh", "Chinese"),
    ("ko", "Korean"),
    ("en", "English"),
    ("vi", "Vietnamese"),
]

STYLE_OPTIONS = [
    ("Balanced Subtitle", "default"),
    ("Comedy / Punchy", "comedy_punchy"),
    ("Faithful + Natural", "faithful_natural"),
    ("Short / Readable", "short_readable"),
    ("Dramatic / Cinematic", "dramatic_cinematic"),
    ("Honorific-aware", "honorifics_cultural"),
    ("Formal (Legacy)", "formal"),
    ("Casual (Legacy)", "casual"),
    ("Keep Honorifics (Legacy)", "keep_honorifics"),
    ("Literal (Legacy)", "literal"),
    ("Custom Prompt", "custom"),
]


class TranslateScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._worker: TaskWorker | None = None

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("OpenAI-compatible", "openai_compatible")
        self.provider_combo.addItem("llama.cpp local", "llama_local")
        self.base_url_edit = QLineEdit()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.model_edit = QLineEdit()
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        for code, label in LANGUAGE_OPTIONS:
            self.source_combo.addItem(label, code)
            self.target_combo.addItem(label, code)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 5000)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 3600)
        self.style_combo = QComboBox()
        for label, value in STYLE_OPTIONS:
            self.style_combo.addItem(label, value)
        self.custom_prompt_edit = QPlainTextEdit()
        self.custom_prompt_edit.setFixedHeight(120)
        self.context_edit = QPlainTextEdit()
        self.context_edit.setFixedHeight(100)

        self.total_label = QLabel("Total: 0")
        self.done_label = QLabel("Translated: 0")
        self.stale_label = QLabel("Stale: 0")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.save_edits_button = QPushButton("Save Edits")
        self.start_button = QPushButton("Start Translation")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        progress_card = QFrame()
        progress_card.setObjectName("Card")
        progress_layout = QHBoxLayout(progress_card)
        progress_layout.setContentsMargins(16, 14, 16, 14)
        progress_layout.setSpacing(14)
        progress_layout.addWidget(QLabel("Total"))
        progress_layout.addWidget(self.total_label)
        progress_layout.addSpacing(12)
        progress_layout.addWidget(QLabel("Translated"))
        progress_layout.addWidget(self.done_label)
        progress_layout.addSpacing(12)
        progress_layout.addWidget(QLabel("Stale"))
        progress_layout.addWidget(self.stale_label)
        progress_layout.addSpacing(18)
        progress_layout.addWidget(self.progress_bar, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self.save_edits_button)
        action_row.addStretch(1)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.stop_button)

        control_card = QFrame()
        control_card.setObjectName("Card")
        form = QFormLayout(control_card)
        form.setContentsMargins(16, 16, 16, 16)
        form.addRow("Provider", self.provider_combo)
        form.addRow("Base URL", self.base_url_edit)
        form.addRow("API Key", self.api_key_edit)
        form.addRow("Model", self.model_edit)
        form.addRow("Source", self.source_combo)
        form.addRow("Target", self.target_combo)
        form.addRow("Batch Size", self.batch_spin)
        form.addRow("Timeout", self.timeout_spin)
        form.addRow("Style", self.style_combo)
        form.addRow("Custom Prompt", self.custom_prompt_edit)
        form.addRow("Context", self.context_edit)

        settings_panel = QWidget()
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)
        settings_layout.addLayout(action_row)
        settings_layout.addWidget(control_card, 1)

        self.table = SubtitleTable()
        table_card = QFrame()
        table_card.setObjectName("Card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(16, 16, 16, 16)
        table_layout.addWidget(QLabel("Translation Editor"))
        table_layout.addWidget(self.table)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.setHandleWidth(10)
        self.content_splitter.addWidget(settings_panel)
        self.content_splitter.addWidget(table_card)
        self.content_splitter.setStretchFactor(0, 3)
        self.content_splitter.setStretchFactor(1, 7)

        self.log_panel = LogPanel()
        log_card = QFrame()
        log_card.setObjectName("Card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_layout.addWidget(QLabel("Log"))
        log_layout.addWidget(self.log_panel)
        self.log_panel.setMinimumHeight(78)

        middle_content = QWidget()
        middle_layout = QVBoxLayout(middle_content)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(14)
        middle_layout.addWidget(progress_card)
        middle_layout.addWidget(self.content_splitter, 1)

        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.setChildrenCollapsible(False)
        self.vertical_splitter.setHandleWidth(10)
        self.vertical_splitter.addWidget(middle_content)
        self.vertical_splitter.addWidget(log_card)
        self.vertical_splitter.setStretchFactor(0, 8)
        self.vertical_splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)
        layout.addWidget(self.vertical_splitter, 1)

        self.save_edits_button.clicked.connect(self.save_edits)
        self.start_button.clicked.connect(self.start_translation)
        self.stop_button.clicked.connect(self.stop_translation)
        self.style_combo.currentIndexChanged.connect(self._update_custom_prompt_state)
        self._update_custom_prompt_state()
        QTimer.singleShot(0, self._apply_initial_splitter_sizes)

    def refresh_from_project(self, project_dir: str | None, manifest: dict | None, table_entries: list[dict]) -> None:
        enabled = bool(project_dir and manifest)
        self.start_button.setEnabled(enabled and self._worker is None)
        self.stop_button.setEnabled(self._worker is not None)
        self.save_edits_button.setEnabled(enabled)
        self.table.load_entries(table_entries, translation_editable=enabled, show_translation=True)

        if not enabled or manifest is None:
            self.total_label.setText("Total: 0")
            self.done_label.setText("Translated: 0")
            self.stale_label.setText("Stale: 0")
            self.progress_bar.setValue(0)
            self.log_panel.clear()
            return

        translator = manifest.get("translator", {})
        self._set_combo_value(self.provider_combo, translator.get("provider", "openai_compatible"))
        self.base_url_edit.setText(str(translator.get("base_url", translator.get("server_url", "")) or ""))
        self.api_key_edit.setText(str(translator.get("api_key", "") or ""))
        self.model_edit.setText(str(translator.get("model", "") or ""))
        self._set_combo_value(self.source_combo, translator.get("source_lang", "auto"))
        self._set_combo_value(self.target_combo, translator.get("target_lang", "vi"))
        self.batch_spin.setValue(int(translator.get("batch_size", 300) or 300))
        self.timeout_spin.setValue(int(translator.get("timeout", 120) or 120))
        self._set_combo_value(self.style_combo, translator.get("style", "default"))
        self.custom_prompt_edit.setPlainText(str(translator.get("custom_prompt", "") or ""))
        self.context_edit.setPlainText(str(manifest.get("context", "") or ""))
        self._update_custom_prompt_state()

        total = len(table_entries)
        translated = len([item for item in table_entries if item.get("translation_text", "")])
        stale = len([item for item in table_entries if item.get("stale")])
        self.total_label.setText(f"Total: {total}")
        self.done_label.setText(f"Translated: {translated}")
        self.stale_label.setText(f"Stale: {stale}")
        self.progress_bar.setValue(int((translated / total) * 100) if total else 0)

    def save_edits(self) -> None:
        edits = self.table.get_translation_edits()
        if not edits:
            QMessageBox.information(self, "No Changes", "There are no translation edits to save.")
            return
        self.main_window.save_translation_edits(edits)
        QMessageBox.information(self, "Saved", "Translation edits saved.")

    def start_translation(self) -> None:
        if not self.main_window.project_dir:
            return
        self.main_window.save_project_translation_settings(self._translator_payload(), self.context_edit.toPlainText().strip())
        self.log_panel.append_log("Starting translation...")
        self._worker = TaskWorker(lambda callback: run_project_translation(self.main_window.project_dir, callback=callback), self)
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
        self.done_label.setText(f"Progress: {current} / {total}")

    def _on_finished(self, success: bool, message: str) -> None:
        if success:
            self.log_panel.append_log("Translation finished.")
        else:
            self.log_panel.append_log(f"Translation stopped: {message}")
        self._worker = None
        self.main_window.reload_current_project()

    def _translator_payload(self) -> dict:
        return {
            "provider": self.provider_combo.currentData(),
            "base_url": self.base_url_edit.text().strip(),
            "server_url": self.base_url_edit.text().strip(),
            "api_key": self.api_key_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "source_lang": self.source_combo.currentData(),
            "target_lang": self.target_combo.currentData(),
            "batch_size": int(self.batch_spin.value()),
            "timeout": int(self.timeout_spin.value()),
            "style": self.style_combo.currentData(),
            "custom_prompt": self.custom_prompt_edit.toPlainText().strip(),
        }

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _update_custom_prompt_state(self) -> None:
        is_custom = self.style_combo.currentData() == "custom"
        self.custom_prompt_edit.setEnabled(is_custom)

    def _apply_initial_splitter_sizes(self) -> None:
        total_width = max(self.width(), 1400)
        self.content_splitter.setSizes([int(total_width * 0.30), int(total_width * 0.70)])
        total_height = max(self.height(), 900)
        self.vertical_splitter.setSizes([int(total_height * 0.84), int(total_height * 0.16)])
