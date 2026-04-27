from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from core.pipeline import ProcessingPipeline
from models.scan_result import ScanResult


class _Signals(QObject):
    progress = pyqtSignal(int, int, str)   # current, total, filename
    finished = pyqtSignal(object)          # ScanResult
    error = pyqtSignal(str)


class ScanWorker(QRunnable):
    def __init__(self, pipeline: ProcessingPipeline, root: Path) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._root = root
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result: ScanResult = self._pipeline.run(
                self._root,
                progress_callback=lambda cur, total, name: self.signals.progress.emit(
                    cur, total, name
                ),
            )
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))
