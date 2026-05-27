from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


class SubtitleTable(QTableWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(0, 6, parent)
        self.setHorizontalHeaderLabels(["#", "Start", "End", "Source", "Translation", "Status"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self._entries: list[dict[str, Any]] = []
        self._translation_editable = True

    def load_entries(self, entries: list[dict[str, Any]], *, translation_editable: bool = True, show_translation: bool = True) -> None:
        self._entries = [dict(item) for item in entries]
        self._translation_editable = translation_editable
        self.setColumnHidden(4, not show_translation)
        self.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self._set_item(row, 0, str(entry.get("index", row + 1)), editable=False)
            self._set_item(row, 1, str(entry.get("start", "")), editable=False)
            self._set_item(row, 2, str(entry.get("end", "")), editable=False)
            self._set_item(row, 3, str(entry.get("source_text", "")), editable=False)
            self._set_item(row, 4, str(entry.get("translation_text", "")), editable=translation_editable and show_translation)
            self._set_item(row, 5, str(entry.get("status_label", "")), editable=False)

    def get_translation_edits(self) -> list[dict[str, Any]]:
        edited: list[dict[str, Any]] = []
        if not self._translation_editable:
            return edited
        for row, entry in enumerate(self._entries):
            item = self.item(row, 4)
            if item is None:
                continue
            new_text = item.text()
            if new_text != str(entry.get("translation_text", "")):
                updated = dict(entry)
                updated["translation_text"] = new_text
                updated["edited"] = True
                edited.append(updated)
        return edited

    def _set_item(self, row: int, column: int, text: str, *, editable: bool) -> None:
        item = QTableWidgetItem(text)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)
