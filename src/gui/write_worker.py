from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from core.exif_writer import ExifWriter
from models.photo_file import WriteResult


class _Signals(QObject):
    progress = pyqtSignal(int, int)   # written, total
    finished = pyqtSignal(list)       # list[WriteResult]
    error = pyqtSignal(str)


class WriteWorker(QRunnable):
    def __init__(
        self,
        writer: ExifWriter,
        tasks: list[tuple[Path, datetime]],
    ) -> None:
        super().__init__()
        self._writer = writer
        self._tasks = tasks
        self.signals = _Signals()

    def run(self) -> None:
        try:
            results: list[WriteResult] = self._writer.write_batch(
                self._tasks,
                progress_callback=lambda cur, total: self.signals.progress.emit(cur, total),
            )
            self.signals.finished.emit(results)
        except Exception as exc:
            self.signals.error.emit(str(exc))
