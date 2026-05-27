from __future__ import annotations

from copy import deepcopy

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


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


class ConfigScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window

        card = QFrame()
        card.setObjectName("Card")
        form = QFormLayout(card)
        form.setContentsMargins(16, 16, 16, 16)

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
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 16384)
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)
        self.style_combo = QComboBox()
        for label, value in STYLE_OPTIONS:
            self.style_combo.addItem(label, value)
        self.custom_prompt_edit = QPlainTextEdit()
        self.custom_prompt_edit.setFixedHeight(140)

        form.addRow("Provider", self.provider_combo)
        form.addRow("Base URL", self.base_url_edit)
        form.addRow("API Key", self.api_key_edit)
        form.addRow("Model", self.model_edit)
        form.addRow("Source", self.source_combo)
        form.addRow("Target", self.target_combo)
        form.addRow("Batch Size", self.batch_spin)
        form.addRow("Timeout", self.timeout_spin)
        form.addRow("Max Tokens", self.max_tokens_spin)
        form.addRow("Retries", self.retries_spin)
        form.addRow("Style", self.style_combo)
        form.addRow("Custom Prompt", self.custom_prompt_edit)
        form.addRow(QLabel("Saved here act as defaults for new translator projects."))

        self.save_button = QPushButton("Save Global Defaults")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(card)
        layout.addWidget(self.save_button)
        layout.addStretch(1)

        self.save_button.clicked.connect(self.save_config)
        self.style_combo.currentIndexChanged.connect(self._update_custom_prompt_state)
        self._update_custom_prompt_state()

    def refresh_from_config(self, config: dict) -> None:
        translator = deepcopy(config.get("translator", {}))
        self._set_combo_value(self.provider_combo, translator.get("provider", "openai_compatible"))
        self.base_url_edit.setText(str(translator.get("base_url", translator.get("server_url", "")) or ""))
        self.api_key_edit.setText(str(translator.get("api_key", "") or ""))
        self.model_edit.setText(str(translator.get("model", "") or ""))
        self._set_combo_value(self.source_combo, translator.get("source_lang", "auto"))
        self._set_combo_value(self.target_combo, translator.get("target_lang", "vi"))
        self.batch_spin.setValue(int(translator.get("batch_size", 300) or 300))
        self.timeout_spin.setValue(int(translator.get("timeout", 120) or 120))
        self.max_tokens_spin.setValue(int(translator.get("max_tokens", 4096) or 4096))
        self.retries_spin.setValue(int(translator.get("max_retries", 2) or 2))
        self._set_combo_value(self.style_combo, translator.get("style", "default"))
        self.custom_prompt_edit.setPlainText(str(translator.get("custom_prompt", "") or ""))
        self._update_custom_prompt_state()

    def save_config(self) -> None:
        config = {
            "translator": {
                "provider": self.provider_combo.currentData(),
                "base_url": self.base_url_edit.text().strip(),
                "server_url": self.base_url_edit.text().strip(),
                "api_key": self.api_key_edit.text().strip(),
                "model": self.model_edit.text().strip(),
                "source_lang": self.source_combo.currentData(),
                "target_lang": self.target_combo.currentData(),
                "batch_size": int(self.batch_spin.value()),
                "timeout": int(self.timeout_spin.value()),
                "max_tokens": int(self.max_tokens_spin.value()),
                "max_retries": int(self.retries_spin.value()),
                "style": self.style_combo.currentData(),
                "custom_prompt": self.custom_prompt_edit.toPlainText().strip(),
            }
        }
        self.main_window.save_global_app_config(config)
        QMessageBox.information(self, "Saved", "Global translator defaults saved.")

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _update_custom_prompt_state(self) -> None:
        self.custom_prompt_edit.setEnabled(self.style_combo.currentData() == "custom")
