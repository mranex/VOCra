from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from vocra_core.exporter import export_ass, export_srt, export_txt
from vocra_core.project_manager import load_project
from vocra_core.text_cleaner import is_meta_ocr_response
from vocra_core.timestamp_utils import get_preferred_timestamp, resolve_end_timestamp
from vocra_gui.widgets.subtitle_table import SubtitleTable


class ExportScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._current_entries: list[dict] = []

        self.original_radio = QRadioButton("Original OCR")
        self.voted_radio = QRadioButton("Draft Voted Text")
        self.translation_radio = QRadioButton("Translation")
        self.original_radio.setChecked(True)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Export Source:"))
        source_row.addWidget(self.original_radio)
        source_row.addWidget(self.voted_radio)
        source_row.addWidget(self.translation_radio)
        source_row.addStretch(1)

        self.table = SubtitleTable()
        table_card = QFrame()
        table_card.setObjectName("Card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(16, 16, 16, 16)
        table_layout.addWidget(self.table)

        self.save_edits_button = QPushButton("Save Edits")
        self.export_srt_button = QPushButton("Export SRT")
        self.export_ass_button = QPushButton("Export ASS")
        self.export_txt_button = QPushButton("Export TXT")

        button_row = QHBoxLayout()
        button_row.addWidget(self.save_edits_button)
        button_row.addStretch(1)
        button_row.addWidget(self.export_srt_button)
        button_row.addWidget(self.export_ass_button)
        button_row.addWidget(self.export_txt_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addLayout(source_row)
        layout.addWidget(table_card, 1)
        layout.addLayout(button_row)

        self.original_radio.toggled.connect(self.reload_table)
        self.voted_radio.toggled.connect(self.reload_table)
        self.translation_radio.toggled.connect(self.reload_table)
        self.save_edits_button.clicked.connect(self.save_edits)
        self.export_srt_button.clicked.connect(lambda: self.export_file("srt"))
        self.export_ass_button.clicked.connect(lambda: self.export_file("ass"))
        self.export_txt_button.clicked.connect(lambda: self.export_file("txt"))

    def refresh_from_project(self, project_dir: str | None, progress: dict | None) -> None:
        enabled = bool(project_dir and progress and progress.get("status", {}).get("segments_done"))
        for widget in (
            self.original_radio,
            self.voted_radio,
            self.translation_radio,
            self.save_edits_button,
            self.export_srt_button,
            self.export_ass_button,
            self.export_txt_button,
        ):
            widget.setEnabled(enabled)

        if not enabled:
            self.table.load_entries([])
            return

        project_path = Path(project_dir)
        status = progress.get("status", {})
        cache_files = progress.get("cache_files", {})
        original_enabled = bool(status.get("ocr_final_done"))
        voted_enabled = bool(status.get("segments_done"))
        translation_path = project_path / str(cache_files.get("translation", "cache/translation.json"))
        translation_enabled = translation_path.exists()

        self.original_radio.setEnabled(original_enabled)
        self.voted_radio.setEnabled(voted_enabled)
        self.translation_radio.setEnabled(translation_enabled)

        if self.translation_radio.isChecked() and not translation_enabled:
            if voted_enabled:
                self.voted_radio.setChecked(True)
            elif original_enabled:
                self.original_radio.setChecked(True)
        elif self.original_radio.isChecked() and not original_enabled:
            if voted_enabled:
                self.voted_radio.setChecked(True)
            elif translation_enabled:
                self.translation_radio.setChecked(True)
        elif self.voted_radio.isChecked() and not voted_enabled:
            if original_enabled:
                self.original_radio.setChecked(True)
            elif translation_enabled:
                self.translation_radio.setChecked(True)
        elif not any(
            (
                self.original_radio.isChecked(),
                self.voted_radio.isChecked(),
                self.translation_radio.isChecked(),
            )
        ):
            if original_enabled:
                self.original_radio.setChecked(True)
            elif voted_enabled:
                self.voted_radio.setChecked(True)
            elif translation_enabled:
                self.translation_radio.setChecked(True)
        self.reload_table()

    def reload_table(self) -> None:
        if not self.main_window.project_dir:
            self.table.load_entries([])
            return
        export_source = self._current_export_source()
        self._current_entries = self._load_entries(self.main_window.project_dir, export_source=export_source)
        self.table.load_entries(self._current_entries)

    def save_edits(self) -> None:
        if not self.main_window.project_dir:
            return
        edits = self.table.get_edited_items()
        if not edits:
            QMessageBox.information(self, "No Changes", "There are no edited rows to save.")
            return
        progress = load_project(self.main_window.project_dir)
        project_path = Path(self.main_window.project_dir)
        if self.translation_radio.isChecked():
            payload_path = project_path / progress["cache_files"]["translation"]
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            items_by_segment = {int(item["segment_id"]): item for item in payload.get("items", [])}
            for item in edits:
                segment_id = int(item["segment_id"])
                if segment_id in items_by_segment:
                    items_by_segment[segment_id]["translation"] = item["text"]
                    items_by_segment[segment_id]["edited"] = True
            payload["items"] = [items_by_segment[key] for key in sorted(items_by_segment)]
            payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        elif self.voted_radio.isChecked():
            payload_path = project_path / progress["cache_files"]["segments"]
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            segments_by_id = {int(item["id"]): item for item in payload.get("segments", [])}
            for item in edits:
                segment_id = int(item["segment_id"])
                if segment_id in segments_by_id:
                    segments_by_id[segment_id]["voted_draft_text"] = item["text"]
                    segments_by_id[segment_id]["edited"] = True
            payload["segments"] = [segments_by_id[key] for key in sorted(segments_by_id)]
            payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            payload_path = project_path / progress["cache_files"]["ocr_final"]
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            items_by_image = {item["image"]: item for item in payload.get("items", [])}
            for item in edits:
                image = item["image"]
                if image in items_by_image:
                    items_by_image[image]["text"] = item["text"]
                    items_by_image[image]["edited"] = True
            payload["items"] = [items_by_image[key] for key in sorted(items_by_image)]
            payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.reload_table()
        QMessageBox.information(self, "Saved", "Edits saved to cache.")

    def export_file(self, kind: str) -> None:
        if not self.main_window.project_dir:
            return
        suffix_map = {"srt": "SubRip (*.srt)", "ass": "ASS (*.ass)", "txt": "Text (*.txt)"}
        output_path, _filter = QFileDialog.getSaveFileName(
            self,
            f"Export {kind.upper()}",
            str(Path(self.main_window.project_dir) / f"subtitle.{kind}"),
            suffix_map[kind],
        )
        if not output_path:
            return
        export_source = self._current_export_source()
        if kind == "srt":
            export_srt(self.main_window.project_dir, output_path, export_source=export_source)
        elif kind == "ass":
            export_ass(self.main_window.project_dir, output_path, export_source=export_source)
        else:
            export_txt(self.main_window.project_dir, output_path, export_source=export_source)
        QMessageBox.information(self, "Exported", f"Exported {kind.upper()} successfully.")

    def _load_entries(self, project_dir: str, *, export_source: str) -> list[dict]:
        progress = load_project(project_dir)
        project_path = Path(project_dir)
        segments = json.loads((project_path / progress["cache_files"]["segments"]).read_text(encoding="utf-8")).get("segments", [])
        timestamps = json.loads((project_path / progress["cache_files"]["timestamp"]).read_text(encoding="utf-8")).get("frames", [])
        timestamp_lookup = {item["image"]: item for item in timestamps}
        frame_order = [str(item["image"]) for item in timestamps]
        interval_sec = float(progress.get("frame_extract", {}).get("interval_sec", 0.5) or 0.5)
        ocr_lookup: dict[str, dict] = {}
        translation_lookup: dict[int, dict] = {}

        if export_source == "final_ocr":
            ocr_path = project_path / progress["cache_files"]["ocr_final"]
            if ocr_path.exists():
                ocr_items = json.loads(ocr_path.read_text(encoding="utf-8")).get("items", [])
                ocr_lookup = {item["image"]: item for item in ocr_items}
        elif export_source == "translation":
            translation_path = project_path / progress["cache_files"]["translation"]
            if translation_path.exists():
                translation_items = json.loads(translation_path.read_text(encoding="utf-8")).get("items", [])
                translation_lookup = {int(item["segment_id"]): item for item in translation_items}

        entries = []
        for index, segment in enumerate(segments, start=1):
            segment_id = int(segment["id"])
            if export_source == "translation":
                text = str(translation_lookup.get(segment_id, {}).get("translation", "") or "")
            elif export_source == "draft_voted":
                text = str(segment.get("voted_draft_text", "") or "")
            else:
                text = str(ocr_lookup.get(segment["represent_image"], {}).get("text", "") or "")
            if is_meta_ocr_response(text):
                text = ""
            entries.append(
                {
                    "index": index,
                    "segment_id": segment_id,
                    "image": segment["represent_image"],
                    "start": get_preferred_timestamp(timestamp_lookup.get(segment["start_image"], {})),
                    "end": resolve_end_timestamp(
                        segment["end_image"],
                        timestamp_lookup=timestamp_lookup,
                        frame_order=frame_order,
                        interval_sec=interval_sec,
                    )
                    if segment["end_image"] in timestamp_lookup
                    else "",
                    "text": text,
                }
            )
        return entries

    def _current_export_source(self) -> str:
        if self.translation_radio.isChecked():
            return "translation"
        if self.voted_radio.isChecked():
            return "draft_voted"
        return "final_ocr"
