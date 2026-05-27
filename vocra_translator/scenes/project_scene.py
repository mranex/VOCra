from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from vocra_translator.widgets.subtitle_table import SubtitleTable


class ProjectScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window

        self.import_button = QPushButton("Import Subtitle File")
        self.open_project_button = QPushButton("Open Project Folder")

        actions_card = QFrame()
        actions_card.setObjectName("Card")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(16, 16, 16, 16)
        actions_layout.setSpacing(10)
        actions_layout.addWidget(self.import_button)
        actions_layout.addWidget(self.open_project_button)
        actions_layout.addStretch(1)

        info_card = QFrame()
        info_card.setObjectName("Card")
        form = QFormLayout(info_card)
        form.setContentsMargins(16, 16, 16, 16)
        self.project_dir_edit = _readonly_line()
        self.source_file_edit = _readonly_line()
        self.format_edit = _readonly_line()
        self.entries_edit = _readonly_line()
        form.addRow("Project Dir", self.project_dir_edit)
        form.addRow("Source File", self.source_file_edit)
        form.addRow("Format", self.format_edit)
        form.addRow("Entries", self.entries_edit)

        self.table = SubtitleTable()
        table_card = QFrame()
        table_card.setObjectName("Card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(16, 16, 16, 16)
        table_layout.addWidget(QLabel("Imported Subtitle"))
        table_layout.addWidget(self.table)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(14)
        left_layout.addWidget(actions_card)
        left_layout.addWidget(info_card)
        left_layout.addStretch(1)

        self.main_splitter = QSplitter()
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(10)
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(table_card)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(self.main_splitter, 1)

        self.import_button.clicked.connect(self.import_subtitle_file)
        self.open_project_button.clicked.connect(self.open_project_folder)
        QTimer.singleShot(0, self._apply_initial_splitter_sizes)

    def refresh_from_project(self, project_dir: str | None, manifest: dict | None, table_entries: list[dict]) -> None:
        self.project_dir_edit.setText(project_dir or "")
        if not project_dir or not manifest:
            self.source_file_edit.setText("")
            self.format_edit.setText("")
            self.entries_edit.setText("0")
            self.table.load_entries([], translation_editable=False, show_translation=False)
            return
        source_file = manifest.get("source_file", {})
        self.source_file_edit.setText(str(source_file.get("original_path", "")))
        self.format_edit.setText(str(source_file.get("format", "")).upper())
        self.entries_edit.setText(str(len(table_entries)))
        self.table.load_entries(table_entries, translation_editable=False, show_translation=False)

    def import_subtitle_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Import Subtitle File",
            str(Path.cwd()),
            "Subtitle Files (*.srt *.ass *.vtt)",
        )
        if path:
            self.main_window.import_subtitle_file(path)

    def open_project_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open Translator Project", str(Path.cwd()))
        if path:
            self.main_window.load_project(path)

    def _apply_initial_splitter_sizes(self) -> None:
        total_width = max(self.width(), 1200)
        self.main_splitter.setSizes([int(total_width * 0.20), int(total_width * 0.80)])


def _readonly_line() -> QLineEdit:
    widget = QLineEdit()
    widget.setReadOnly(True)
    return widget
