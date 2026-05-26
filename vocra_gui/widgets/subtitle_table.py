from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


class SubtitleTable(QTableWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["#", "Start", "End", "Text"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self._entries: list[dict[str, Any]] = []

    def load_entries(self, entries: list[dict[str, Any]]) -> None:
        self._entries = [dict(entry) for entry in entries]
        self.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self._set_item(row, 0, str(entry.get("index", row + 1)), editable=False)
            self._set_item(row, 1, str(entry.get("start", "")), editable=False)
            self._set_item(row, 2, str(entry.get("end", "")), editable=False)
            self._set_item(row, 3, str(entry.get("text", "")), editable=True)

    def get_edited_items(self) -> list[dict[str, Any]]:
        edited: list[dict[str, Any]] = []
        for row, entry in enumerate(self._entries):
            item = self.item(row, 3)
            if item is None:
                continue
            text = item.text()
            if text != str(entry.get("text", "")):
                updated = dict(entry)
                updated["text"] = text
                updated["edited"] = True
                edited.append(updated)
        return edited

    def _set_item(self, row: int, column: int, text: str, *, editable: bool) -> None:
        item = QTableWidgetItem(text)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)
