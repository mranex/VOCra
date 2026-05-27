from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocra_core.final_ocr.llama_server_manager import LlamaServerManager


class ConfigScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window

        container = QWidget()
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(18, 18, 18, 18)
        self.container_layout.setSpacing(14)

        self._build_draft_group()
        self._build_segmenter_group()
        self._build_final_group()
        self._build_translator_group()

        self.save_button = QPushButton("Save Config")
        self.save_button.clicked.connect(self.save_config)
        self.container_layout.addWidget(self.save_button)
        self.container_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def refresh_from_project(self, project_dir: str | None, progress: dict | None) -> None:
        self.save_button.setEnabled(True)
        global_config = self.main_window.global_config
        draft = global_config.get("draft_ocr", {})
        ssim_filter = global_config.get("ssim_filter", {})
        segmenter = global_config.get("segmenter", {})
        final = global_config.get("final_ocr", {})
        translator = global_config.get("translator", {})

        self._set_combo_data(self.draft_language_combo, draft.get("language", "auto"))
        self.ssim_enabled_check.setChecked(bool(ssim_filter.get("enabled", True)))
        self.ssim_threshold_spin.setValue(float(ssim_filter.get("threshold", 0.95) or 0.95))
        self.segment_similarity_spin.setValue(float(segmenter.get("similarity_threshold", 0.5) or 0.5))
        self.segment_blank_tolerance_spin.setValue(int(segmenter.get("blank_tolerance", 1) or 1))
        self.segment_ssim_cross_check_check.setChecked(bool(segmenter.get("ssim_cross_check", True)))
        self.segment_ssim_same_spin.setValue(float(segmenter.get("ssim_same_threshold", 0.7) or 0.7))
        self.segment_ssim_override_spin.setValue(float(segmenter.get("ssim_override_threshold", 0.9) or 0.9))
        self.segment_use_sharpness_check.setChecked(bool(segmenter.get("use_sharpness_representative", True)))
        self.segment_use_text_voting_check.setChecked(bool(segmenter.get("use_text_voting", True)))
        self._set_combo_data(self.final_provider_combo, final.get("provider", "llama_cpp"))
        self.final_server_url_edit.setText(str(final.get("server_url", "")))
        self.final_model_edit.setText(str(final.get("model", "")))
        self.final_prompt_edit.setText(str(final.get("prompt", "")))
        self.final_timeout_spin.setValue(int(final.get("timeout", 120) or 120))
        self.final_tokens_spin.setValue(int(final.get("max_tokens", 512) or 512))
        self.final_temp_spin.setValue(float(final.get("temperature", 0) or 0))
        self.llama_dir_edit.setText(str(final.get("llama_cpp_dir", "")))
        self.llama_model_edit.setText(str(final.get("model_path", "")))
        self.llama_mmproj_edit.setText(str(final.get("mmproj_path", "")))
        self.llama_gpu_spin.setValue(int(final.get("gpu_layers", 99) or 99))
        self.llama_ctx_spin.setValue(int(final.get("ctx_size", 8192) or 8192))
        self.llama_parallel_spin.setValue(int(final.get("parallel_slots", 1) or 1))
        self.chrome_language_edit.setText(str(final.get("chrome_lens_language", "auto")))
        self.chrome_headless_check.setChecked(bool(final.get("chrome_lens_headless", True)))
        self.chrome_retry_spin.setValue(int(final.get("chrome_lens_max_retries", 3) or 3))
        self.chrome_path_edit.setText(str(final.get("chrome_path", "")))
        self.chrome_user_data_edit.setText(str(final.get("user_data_dir", "")))

        self._set_combo_data(self.translator_provider_combo, translator.get("provider", "openai_compatible"))
        self.translator_base_url_edit.setText(str(translator.get("base_url", translator.get("server_url", ""))))
        self.translator_api_key_edit.setText(str(translator.get("api_key", "")))
        self.translator_model_edit.setText(str(translator.get("model", "")))
        self._set_combo_data(self.translator_source_combo, translator.get("source_lang", "auto"))
        self._set_combo_data(self.translator_target_combo, translator.get("target_lang", "vi"))
        self.translator_batch_spin.setValue(int(translator.get("batch_size", 300) or 300))
        self.translator_timeout_spin.setValue(int(translator.get("timeout", 120) or 120))
        self._set_combo_data(self.translator_style_combo, translator.get("style", "default"))
        self.translator_custom_prompt_edit.setPlainText(str(translator.get("custom_prompt", "") or ""))
        self._update_provider_visibility()
        self._update_translator_prompt_visibility()

    def save_config(self) -> None:
        config = deepcopy(self.main_window.global_config)
        config.setdefault("ssim_filter", {})
        config.setdefault("segmenter", {})
        config["draft_ocr"]["language"] = self.draft_language_combo.currentData()
        config["ssim_filter"]["enabled"] = self.ssim_enabled_check.isChecked()
        config["ssim_filter"]["threshold"] = float(self.ssim_threshold_spin.value())
        config["segmenter"]["similarity_threshold"] = float(self.segment_similarity_spin.value())
        config["segmenter"]["blank_tolerance"] = int(self.segment_blank_tolerance_spin.value())
        config["segmenter"]["ssim_cross_check"] = self.segment_ssim_cross_check_check.isChecked()
        config["segmenter"]["ssim_same_threshold"] = float(self.segment_ssim_same_spin.value())
        config["segmenter"]["ssim_override_threshold"] = float(self.segment_ssim_override_spin.value())
        config["segmenter"]["use_sharpness_representative"] = self.segment_use_sharpness_check.isChecked()
        config["segmenter"]["use_text_voting"] = self.segment_use_text_voting_check.isChecked()

        final = config["final_ocr"]
        final["provider"] = self.final_provider_combo.currentData()
        final["server_url"] = self.final_server_url_edit.text().strip()
        final["model"] = self.final_model_edit.text().strip()
        final["prompt"] = self.final_prompt_edit.text().strip()
        final["timeout"] = int(self.final_timeout_spin.value())
        final["max_tokens"] = int(self.final_tokens_spin.value())
        final["temperature"] = float(self.final_temp_spin.value())
        final["llama_cpp_dir"] = self.llama_dir_edit.text().strip()
        final["model_path"] = self.llama_model_edit.text().strip()
        final["mmproj_path"] = self.llama_mmproj_edit.text().strip()
        final["gpu_layers"] = int(self.llama_gpu_spin.value())
        final["ctx_size"] = int(self.llama_ctx_spin.value())
        final["parallel_slots"] = int(self.llama_parallel_spin.value())
        final["chrome_lens_language"] = self.chrome_language_edit.text().strip() or "auto"
        final["chrome_lens_headless"] = self.chrome_headless_check.isChecked()
        final["chrome_lens_max_retries"] = int(self.chrome_retry_spin.value())
        final["chrome_path"] = self.chrome_path_edit.text().strip()
        final["user_data_dir"] = self.chrome_user_data_edit.text().strip()

        translator = config["translator"]
        translator["provider"] = self.translator_provider_combo.currentData()
        translator["base_url"] = self.translator_base_url_edit.text().strip()
        translator["server_url"] = self.translator_base_url_edit.text().strip()
        translator["api_key"] = self.translator_api_key_edit.text().strip()
        translator["model"] = self.translator_model_edit.text().strip()
        translator["source_lang"] = self.translator_source_combo.currentData()
        translator["target_lang"] = self.translator_target_combo.currentData()
        translator["batch_size"] = int(self.translator_batch_spin.value())
        translator["timeout"] = int(self.translator_timeout_spin.value())
        translator["style"] = self.translator_style_combo.currentData()
        translator["custom_prompt"] = self.translator_custom_prompt_edit.toPlainText().strip()

        self.main_window.save_global_app_config(config)
        QMessageBox.information(
            self,
            "Saved",
            "Global app configuration saved.\nAPI key is stored outside the repo in your user config folder.",
        )

    def _build_draft_group(self) -> None:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QFormLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        self.draft_language_combo = QComboBox()
        for code, label in [("auto", "Auto"), ("ja", "Japanese"), ("zh", "Chinese"), ("en", "English")]:
            self.draft_language_combo.addItem(label, code)
        layout.addRow("Draft OCR Language", self.draft_language_combo)
        self.ssim_enabled_check = QCheckBox("Enable SSIM pre-filter")
        self.ssim_threshold_spin = QDoubleSpinBox()
        self.ssim_threshold_spin.setRange(0.80, 1.00)
        self.ssim_threshold_spin.setDecimals(2)
        self.ssim_threshold_spin.setSingleStep(0.01)
        self.ssim_threshold_spin.setValue(0.95)
        self.ssim_threshold_spin.setToolTip("Higher = only nearly identical frames are skipped before Draft OCR.")
        layout.addRow("SSIM Filter", self.ssim_enabled_check)
        layout.addRow("SSIM Threshold", self.ssim_threshold_spin)
        self.container_layout.addWidget(_with_title("Draft OCR + SSIM", frame))

    def _build_segmenter_group(self) -> None:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QFormLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)

        self.segment_similarity_spin = QDoubleSpinBox()
        self.segment_similarity_spin.setRange(0.0, 1.0)
        self.segment_similarity_spin.setDecimals(2)
        self.segment_similarity_spin.setSingleStep(0.05)
        self.segment_similarity_spin.setValue(0.5)

        self.segment_blank_tolerance_spin = QSpinBox()
        self.segment_blank_tolerance_spin.setRange(0, 10)
        self.segment_blank_tolerance_spin.setValue(1)
        self.segment_blank_tolerance_spin.setToolTip(
            "So blank frames lien tiep cho phep truoc khi dong segment. 0 = dong ngay."
        )
        self.segment_ssim_cross_check_check = QCheckBox("Enable SSIM cross-check")
        self.segment_ssim_same_spin = QDoubleSpinBox()
        self.segment_ssim_same_spin.setRange(0.5, 1.0)
        self.segment_ssim_same_spin.setDecimals(2)
        self.segment_ssim_same_spin.setSingleStep(0.05)
        self.segment_ssim_same_spin.setValue(0.7)

        self.segment_ssim_override_spin = QDoubleSpinBox()
        self.segment_ssim_override_spin.setRange(0.5, 1.0)
        self.segment_ssim_override_spin.setDecimals(2)
        self.segment_ssim_override_spin.setSingleStep(0.05)
        self.segment_ssim_override_spin.setValue(0.9)
        self.segment_use_sharpness_check = QCheckBox("Use sharpness-based representative selection")
        self.segment_use_sharpness_check.setChecked(True)
        self.segment_use_text_voting_check = QCheckBox("Enable text voting")
        self.segment_use_text_voting_check.setChecked(True)

        layout.addRow("Text Similarity", self.segment_similarity_spin)
        layout.addRow("Blank Tolerance", self.segment_blank_tolerance_spin)
        layout.addRow("SSIM Cross-check", self.segment_ssim_cross_check_check)
        layout.addRow("SSIM Same Threshold", self.segment_ssim_same_spin)
        layout.addRow("SSIM Override Threshold", self.segment_ssim_override_spin)
        layout.addRow("Sharpness Representative", self.segment_use_sharpness_check)
        layout.addRow("Text Voting", self.segment_use_text_voting_check)
        self.container_layout.addWidget(_with_title("Segmenter", frame))

    def _build_final_group(self) -> None:
        self.final_section = QWidget()
        outer = QVBoxLayout(self.final_section)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        final_card = QFrame()
        final_card.setObjectName("Card")
        layout = QFormLayout(final_card)
        layout.setContentsMargins(16, 16, 16, 16)

        self.final_provider_combo = QComboBox()
        self.final_provider_combo.addItem("llama.cpp local", "llama_cpp")
        self.final_provider_combo.addItem("Chrome Lens", "chrome_lens")
        self.final_provider_combo.addItem("OpenAI-compatible API", "openai_compatible")
        self.final_provider_combo.currentIndexChanged.connect(self._update_provider_visibility)

        self.final_server_url_edit = QLineEdit()
        self.final_model_edit = QLineEdit()
        self.final_prompt_edit = QLineEdit()
        self.final_timeout_spin = QSpinBox()
        self.final_timeout_spin.setRange(1, 3600)
        self.final_tokens_spin = QSpinBox()
        self.final_tokens_spin.setRange(1, 16384)
        self.final_temp_spin = QDoubleSpinBox()
        self.final_temp_spin.setRange(0.0, 2.0)
        self.final_temp_spin.setSingleStep(0.1)

        layout.addRow("Provider", self.final_provider_combo)
        layout.addRow("Server URL", self.final_server_url_edit)
        layout.addRow("Model", self.final_model_edit)
        layout.addRow("Prompt", self.final_prompt_edit)
        layout.addRow("Timeout", self.final_timeout_spin)
        layout.addRow("Max Tokens", self.final_tokens_spin)
        layout.addRow("Temperature", self.final_temp_spin)

        self.llama_card = QFrame()
        self.llama_card.setObjectName("Card")
        llama_layout = QGridLayout(self.llama_card)
        llama_layout.setContentsMargins(16, 16, 16, 16)
        llama_layout.setHorizontalSpacing(10)
        llama_layout.setVerticalSpacing(10)

        self.llama_dir_edit = QLineEdit()
        self.llama_model_edit = QLineEdit()
        self.llama_mmproj_edit = QLineEdit()
        self.llama_gpu_spin = QSpinBox()
        self.llama_gpu_spin.setRange(0, 512)
        self.llama_ctx_spin = QSpinBox()
        self.llama_ctx_spin.setRange(256, 65536)
        self.llama_ctx_spin.setSingleStep(256)
        self.llama_ctx_spin.setValue(8192)
        self.llama_parallel_spin = QSpinBox()
        self.llama_parallel_spin.setRange(1, 64)
        self.llama_parallel_spin.setValue(1)

        browse_llama_model = QPushButton("Browse Model")
        browse_llama_mmproj = QPushButton("Browse mmproj")
        browse_llama_model.clicked.connect(lambda: self._browse_into(self.llama_model_edit, "Select Model"))
        browse_llama_mmproj.clicked.connect(lambda: self._browse_into(self.llama_mmproj_edit, "Select mmproj"))

        self.create_bat_button = QPushButton("Create .bat")
        self.open_folder_button = QPushButton("Open Folder")
        self.start_server_button = QPushButton("Start")
        self.check_server_button = QPushButton("Check")
        self.create_bat_button.clicked.connect(self._create_bat)
        self.open_folder_button.clicked.connect(self._open_server_folder)
        self.start_server_button.clicked.connect(self._start_server)
        self.check_server_button.clicked.connect(self._check_server)

        llama_layout.addWidget(QLabel("llama.cpp Dir"), 0, 0)
        llama_layout.addWidget(self.llama_dir_edit, 0, 1, 1, 2)
        llama_layout.addWidget(QLabel("Model Path"), 1, 0)
        llama_layout.addWidget(self.llama_model_edit, 1, 1)
        llama_layout.addWidget(browse_llama_model, 1, 2)
        llama_layout.addWidget(QLabel("mmproj Path"), 2, 0)
        llama_layout.addWidget(self.llama_mmproj_edit, 2, 1)
        llama_layout.addWidget(browse_llama_mmproj, 2, 2)
        llama_layout.addWidget(QLabel("GPU Layers"), 3, 0)
        llama_layout.addWidget(self.llama_gpu_spin, 3, 1)
        llama_layout.addWidget(QLabel("Context"), 3, 2)
        llama_layout.addWidget(self.llama_ctx_spin, 3, 3)
        llama_layout.addWidget(QLabel("Parallel Slots"), 4, 0)
        llama_layout.addWidget(self.llama_parallel_spin, 4, 1)

        action_row = QHBoxLayout()
        action_row.addWidget(self.create_bat_button)
        action_row.addWidget(self.open_folder_button)
        action_row.addWidget(self.start_server_button)
        action_row.addWidget(self.check_server_button)
        action_row.addStretch(1)
        llama_layout.addLayout(action_row, 5, 0, 1, 4)

        self.chrome_card = QFrame()
        self.chrome_card.setObjectName("Card")
        chrome_layout = QFormLayout(self.chrome_card)
        chrome_layout.setContentsMargins(16, 16, 16, 16)
        self.chrome_language_edit = QLineEdit()
        self.chrome_headless_check = QCheckBox("Headless")
        self.chrome_retry_spin = QSpinBox()
        self.chrome_retry_spin.setRange(0, 10)
        self.chrome_path_edit = QLineEdit()
        self.chrome_user_data_edit = QLineEdit()
        chrome_layout.addRow("Language", self.chrome_language_edit)
        chrome_layout.addRow("Headless", self.chrome_headless_check)
        chrome_layout.addRow("Max Retries", self.chrome_retry_spin)
        chrome_layout.addRow("Chrome Path", self.chrome_path_edit)
        chrome_layout.addRow("User Data Dir", self.chrome_user_data_edit)

        outer.addWidget(_with_title("Final OCR", final_card))
        outer.addWidget(_with_title("llama.cpp Server", self.llama_card))
        outer.addWidget(_with_title("Chrome Lens", self.chrome_card))
        self.container_layout.addWidget(self.final_section)

    def _build_translator_group(self) -> None:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QFormLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)

        self.translator_provider_combo = QComboBox()
        self.translator_provider_combo.addItem("OpenAI-compatible", "openai_compatible")
        self.translator_provider_combo.addItem("llama.cpp local", "llama_local")
        self.translator_base_url_edit = QLineEdit()
        self.translator_api_key_edit = QLineEdit()
        self.translator_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.translator_model_edit = QLineEdit()
        self.translator_source_combo = QComboBox()
        self.translator_target_combo = QComboBox()
        for code, label in [("auto", "Auto"), ("ja", "Japanese"), ("en", "English"), ("vi", "Vietnamese")]:
            self.translator_source_combo.addItem(label, code)
            self.translator_target_combo.addItem(label, code)
        self.translator_batch_spin = QSpinBox()
        self.translator_batch_spin.setRange(1, 5000)
        self.translator_timeout_spin = QSpinBox()
        self.translator_timeout_spin.setRange(1, 3600)
        self.translator_style_combo = QComboBox()
        for label, value in (
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
        ):
            self.translator_style_combo.addItem(label, value)
        self.translator_style_combo.currentIndexChanged.connect(self._update_translator_prompt_visibility)
        self.translator_custom_prompt_edit = QPlainTextEdit()
        self.translator_custom_prompt_edit.setPlaceholderText(
            "Used only when Style = Custom Prompt.\n"
            "Write role, rules, tone, forbidden behaviors, terminology preferences, etc."
        )
        self.translator_custom_prompt_edit.setFixedHeight(140)
        self.translator_custom_prompt_hint = QLabel(
            "Prompt sent to the model will use either: selected Style + project video info, or Custom Prompt + project video info."
        )
        self.translator_custom_prompt_hint.setWordWrap(True)

        layout.addRow("Provider", self.translator_provider_combo)
        layout.addRow("Base URL", self.translator_base_url_edit)
        layout.addRow("API Key", self.translator_api_key_edit)
        layout.addRow("Model", self.translator_model_edit)
        layout.addRow("Source", self.translator_source_combo)
        layout.addRow("Target", self.translator_target_combo)
        layout.addRow("Batch Size", self.translator_batch_spin)
        layout.addRow("Timeout", self.translator_timeout_spin)
        layout.addRow("Style", self.translator_style_combo)
        layout.addRow("Custom Prompt", self.translator_custom_prompt_edit)
        layout.addRow(self.translator_custom_prompt_hint)
        note = QLabel("API key is stored in a user-local config file outside this repo.")
        note.setWordWrap(True)
        layout.addRow(note)
        self.container_layout.addWidget(_with_title("Translator", frame))

    def _browse_into(self, line_edit: QLineEdit, title: str) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, title, str(Path.cwd()), "GGUF Files (*.gguf);;All Files (*.*)")
        if path:
            line_edit.setText(path)

    def _manager_from_form(self) -> LlamaServerManager:
        return LlamaServerManager(
            llama_cpp_dir=self.llama_dir_edit.text().strip(),
            model_path=self.llama_model_edit.text().strip(),
            mmproj_path=self.llama_mmproj_edit.text().strip(),
            server_url=self.final_server_url_edit.text().strip(),
            gpu_layers=int(self.llama_gpu_spin.value()),
            ctx_size=int(self.llama_ctx_spin.value()),
            parallel_slots=int(self.llama_parallel_spin.value()),
            temperature=float(self.final_temp_spin.value()),
            workspace_root=str(Path.cwd()),
        )

    def _create_bat(self) -> None:
        manager = self._manager_from_form()
        path = manager.write_run_server_bat()
        QMessageBox.information(self, "Created", f"Created run_server.bat at:\n{path}")

    def _open_server_folder(self) -> None:
        manager = self._manager_from_form()
        path = manager.open_server_folder()
        QMessageBox.information(self, "Opened", f"Opened server folder:\n{path}")

    def _start_server(self) -> None:
        manager = self._manager_from_form()
        path = manager.start_external()
        QMessageBox.information(self, "Started", f"Started server using:\n{path}")

    def _check_server(self) -> None:
        manager = self._manager_from_form()
        alive, message = manager.check_health()
        QMessageBox.information(self, "Health Check", message if alive else f"Not ready:\n{message}")

    def _update_provider_visibility(self) -> None:
        provider = self.final_provider_combo.currentData()
        self.llama_card.setVisible(provider == "llama_cpp")
        self.chrome_card.setVisible(provider == "chrome_lens")

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        elif combo.count() > 0:
            combo.setCurrentIndex(0)

    def _update_translator_prompt_visibility(self) -> None:
        is_custom = self.translator_style_combo.currentData() == "custom"
        self.translator_custom_prompt_edit.setEnabled(is_custom)
        self.translator_custom_prompt_hint.setText(
            "Prompt sent to the model will use: Custom Prompt + project video info."
            if is_custom
            else "Prompt sent to the model will use: selected Style preset + project video info."
        )


def _with_title(title: str, widget: QWidget) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    label = QLabel(title)
    label.setStyleSheet("font-size: 12pt; font-weight: 700; color: #00bcd4;")
    layout.addWidget(label)
    layout.addWidget(widget)
    return container
