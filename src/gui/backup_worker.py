from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from core.backup_pipeline import BackupPipeline
from models.backup_file import BackupFile, BackupResult, CopyResult


class BackupWorker(QRunnable):
    """Run BackupPipeline.run() on a thread-pool thread."""

    class _Signals(QObject):
        progress = pyqtSignal(str, int, int, str)   # stage, current, total, name
        finished = pyqtSignal(object)               # BackupResult
        error = pyqtSignal(str)

    def __init__(
        self,
        pipeline: BackupPipeline,
        sources: list[Path],
        destination: Path,
        force_rehash: bool = False,
    ) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._sources = sources
        self._destination = destination
        self._force_rehash = force_rehash
        self.signals = self._Signals()

    def run(self) -> None:
        try:
            if self._force_rehash:
                self._pipeline._cache.clear_all()
            result = self._pipeline.run(
                self._sources,
                self._destination,
                progress_callback=self.signals.progress.emit,
            )
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class CopyWorker(QRunnable):
    """Run BackupPipeline.copy_unique() on a thread-pool thread."""

    class _Signals(QObject):
        progress = pyqtSignal(int, int, str)    # current, total, filename
        finished = pyqtSignal(list)             # list[CopyResult]
        error = pyqtSignal(str)

    def __init__(
        self,
        pipeline: BackupPipeline,
        result: BackupResult,
        files: list[BackupFile] | None = None,
    ) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._result = result
        self._files = files
        self.signals = self._Signals()

    def run(self) -> None:
        try:
            copy_results = self._pipeline.copy_unique(
                self._result,
                files=self._files,
                progress_callback=self.signals.progress.emit,
            )
            self.signals.finished.emit(copy_results)
        except Exception as exc:
            self.signals.error.emit(str(exc))
