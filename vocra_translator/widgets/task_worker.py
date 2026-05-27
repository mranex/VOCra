from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal


class TaskWorker(QThread):
    progress = Signal(int, int, str)
    log_message = Signal(str)
    finished_with_status = Signal(bool, str)

    def __init__(self, task_fn: Callable[[Callable[[int, int | None, str], None]], None], parent=None) -> None:
        super().__init__(parent)
        self._task_fn = task_fn

    def run(self) -> None:
        try:
            self._task_fn(self._emit_progress)
            if self.isInterruptionRequested():
                self.finished_with_status.emit(False, "Cancelled")
            else:
                self.finished_with_status.emit(True, "")
        except Exception as exc:
            message = "Cancelled" if self.isInterruptionRequested() else str(exc)
            self.finished_with_status.emit(False, message)

    def _emit_progress(self, current: int, total: int | None, message: str) -> None:
        if self.isInterruptionRequested():
            raise RuntimeError("Cancelled")
        resolved_total = int(total if total is not None else max(current, 1))
        text = str(message or "")
        self.progress.emit(int(current), resolved_total, text)
        self.log_message.emit(text)
