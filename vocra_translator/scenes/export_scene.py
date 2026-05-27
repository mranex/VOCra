from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vocra_translator.core.export_service import build_default_export_name, export_project_subtitles
from vocra_translator.core.format_registry import supported_formats
from vocra_translator.widgets.subtitle_table import SubtitleTable


class ExportScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window

        self.source_combo = QComboBox()
        self.source_combo.addItem("Translation", "translation")
        self.source_combo.addItem("Source", "source")
        self.format_combo = QComboBox()
        for value in supported_formats():
            self.format_combo.addItem(value.upper(), value)

        self.table = SubtitleTable()
        table_card = QFrame()
        table_card.setObjectName("Card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(16, 16, 16, 16)
        table_layout.addWidget(QLabel("Export Preview"))
        table_layout.addWidget(self.table)

        control_row = QHBoxLayout()
        control_row.addWidget(QLabel("Text Source"))
        control_row.addWidget(self.source_combo)
        control_row.addWidget(QLabel("Target Format"))
        control_row.addWidget(self.format_combo)
        control_row.addStretch(1)

        self.save_edits_button = QPushButton("Save Edits")
        self.export_button = QPushButton("Export File")

        button_row = QHBoxLayout()
        button_row.addWidget(self.save_edits_button)
        button_row.addStretch(1)
        button_row.addWidget(self.export_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addLayout(button_row)
        layout.addLayout(control_row)
        layout.addWidget(table_card, 1)

        self.save_edits_button.clicked.connect(self.save_edits)
        self.export_button.clicked.connect(self.export_file)

    def refresh_from_project(self, project_dir: str | None, manifest: dict | None, table_entries: list[dict]) -> None:
        enabled = bool(project_dir and manifest)
        self.save_edits_button.setEnabled(enabled)
        self.export_button.setEnabled(enabled)
        self.source_combo.setEnabled(enabled)
        self.format_combo.setEnabled(enabled)
        self.table.load_entries(table_entries, translation_editable=enabled, show_translation=True)

        if manifest:
            current_format = str(manifest.get("source_file", {}).get("format", "srt") or "srt")
            index = self.format_combo.findData(current_format)
            if index >= 0:
                self.format_combo.setCurrentIndex(index)

    def save_edits(self) -> None:
        edits = self.table.get_translation_edits()
        if not edits:
            QMessageBox.information(self, "No Changes", "There are no translation edits to save.")
            return
        self.main_window.save_translation_edits(edits)
        QMessageBox.information(self, "Saved", "Translation edits saved.")

    def export_file(self) -> None:
        if not self.main_window.project_dir or not self.main_window.manifest:
            return
        self.main_window.save_translation_edits(self.table.get_translation_edits())
        target_format = str(self.format_combo.currentData() or "srt")
        default_name = build_default_export_name(self.main_window.manifest, target_format=target_format)
        default_path = Path(self.main_window.project_dir) / "exports" / default_name
        output_path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export Subtitle",
            str(default_path),
            "Subtitle Files (*.srt *.ass *.vtt)",
        )
        if not output_path:
            return
        written = export_project_subtitles(
            self.main_window.project_dir,
            output_path=output_path,
            target_format=target_format,
            text_source=str(self.source_combo.currentData() or "translation"),
        )
        QMessageBox.information(self, "Exported", f"Subtitle exported to:\n{written}")
