from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QToolButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from core.exif_writer import ExifWriter
from core.exiftool_checker import check_exiftool
from core.pipeline import ProcessingPipeline
from gui.conflict_dialog import ConflictDialog
from gui.results_table import ResultsTableView
from gui.scan_worker import ScanWorker
from gui.settings_dialog import SettingsDialog
from gui.write_worker import WriteWorker
from models.photo_file import PhotoFile, WriteResult
from models.scan_result import ScanResult

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PhotosMetadata")
        self.resize(1100, 700)

        self._scan_result: ScanResult | None = None
        self._thread_pool = QThreadPool.globalInstance()

        self._build_ui()
        self._check_exiftool_on_startup()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self._select_btn = QPushButton("Select Directory…")
        self._select_btn.clicked.connect(self._on_select_directory)
        toolbar.addWidget(self._select_btn)

        self._path_label = QLabel("No directory selected")
        self._path_label.setWordWrap(False)
        toolbar.addWidget(self._path_label, stretch=1)

        self._scan_btn = QPushButton("Scan")
        self._scan_btn.setEnabled(False)
        self._scan_btn.clicked.connect(self._on_scan_clicked)
        toolbar.addWidget(self._scan_btn)

        # Apply button with dropdown
        self._apply_btn = QToolButton()
        self._apply_btn.setText("Apply Dates ▾")
        self._apply_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._apply_btn.setEnabled(False)
        apply_menu = QMenu(self._apply_btn)
        apply_menu.addAction("Apply All Auto-Resolved", self._on_apply_all)
        apply_menu.addAction("Apply Selected Rows", self._on_apply_selected)
        self._apply_btn.setMenu(apply_menu)
        self._apply_btn.clicked.connect(self._on_apply_all)
        toolbar.addWidget(self._apply_btn)

        settings_btn = QPushButton("⚙")
        settings_btn.setFixedWidth(32)
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self._on_settings)
        toolbar.addWidget(settings_btn)

        layout.addLayout(toolbar)

        # ── Results table ────────────────────────────────────────────────────
        self._table = ResultsTableView()
        layout.addWidget(self._table, stretch=1)

        # ── Status bar ───────────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._status_label = QLabel("Ready")
        self._status_bar.addWidget(self._status_label, stretch=1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress_bar)

        self._root: Path | None = None

    # ── Startup ──────────────────────────────────────────────────────────────

    def _check_exiftool_on_startup(self) -> None:
        path = SettingsDialog.exiftool_path()
        ok, msg = check_exiftool(path)
        if not ok:
            QMessageBox.warning(
                self,
                "ExifTool Not Found",
                f"ExifTool could not be found:\n{msg}\n\n"
                "Install ExifTool and set its path in Settings before scanning.\n\n"
                "  macOS:   brew install exiftool\n"
                "  Linux:   sudo apt install libimage-exiftool-perl\n"
                "  Windows: https://exiftool.org",
            )
            self._scan_btn.setEnabled(False)
        else:
            logger.info("ExifTool version %s", msg)

    # ── Directory selection ───────────────────────────────────────────────────

    def _on_select_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Photo Directory")
        if directory:
            self._root = Path(directory)
            self._path_label.setText(directory)
            self._scan_btn.setEnabled(True)
            self._apply_btn.setEnabled(False)
            self._scan_result = None
            self._table.source_model().update(
                ScanResult(root_dir=self._root, files=[])
            )
            self._status_label.setText("Directory selected. Click Scan to start.")

    # ── Scan ─────────────────────────────────────────────────────────────────

    def _on_scan_clicked(self) -> None:
        if self._root is None:
            return

        et_path = SettingsDialog.exiftool_path()
        ok, msg = check_exiftool(et_path)
        if not ok:
            QMessageBox.critical(self, "ExifTool Error",
                                 f"ExifTool not available:\n{msg}")
            return

        self._scan_btn.setEnabled(False)
        self._apply_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(True)
        self._status_label.setText("Scanning…")

        pipeline = ProcessingPipeline.create(exiftool_path=et_path)
        worker = ScanWorker(pipeline, self._root)
        worker.signals.progress.connect(self._on_scan_progress)
        worker.signals.finished.connect(self._on_scan_complete)
        worker.signals.error.connect(self._on_scan_error)
        self._thread_pool.start(worker)

    def _on_scan_progress(self, current: int, total: int, name: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._status_label.setText(f"Scanning {current}/{total}: {name}")

    def _on_scan_complete(self, result: ScanResult) -> None:
        self._scan_result = result
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)

        self._table.load_result(result)

        summary = (
            f"{result.total} files  |  "
            f"{len(result.has_exif)} ✅  |  "
            f"{len(result.missing)} ❌  |  "
            f"{len(result.auto_queue)} ⚠️ auto  |  "
            f"{len(result.needs_user)} ⚠️ conflict"
        )
        self._status_label.setText(summary)

        # Auto-show conflict dialog if needed
        if result.needs_user:
            reply = QMessageBox.question(
                self,
                "Date Conflicts Found",
                f"{len(result.needs_user)} file(s) have conflicting date sources.\n"
                "Would you like to resolve them now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._show_conflict_dialogs()

        can_apply = bool(result.auto_queue or result.needs_user)
        self._apply_btn.setEnabled(can_apply)

    def _on_scan_error(self, error: str) -> None:
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._status_label.setText(f"Scan error: {error}")
        QMessageBox.critical(self, "Scan Error", error)

    # ── Conflict resolution ───────────────────────────────────────────────────

    def _show_conflict_dialogs(self) -> None:
        if self._scan_result is None:
            return
        conflicts = self._scan_result.needs_user
        if not conflicts:
            return

        dialog = ConflictDialog(conflicts, parent=self)
        dialog.exec()

        # Apply user's choices back to the scan result
        for file in conflicts:
            chosen = dialog.chosen_dates.get(file.path)
            if chosen is not None:
                updated = replace(file, chosen_date=chosen, status="resolved_single")
                self._table.source_model().update_file(file.path, updated)
                # Update in scan_result too
                for i, f in enumerate(self._scan_result.files):
                    if f.path == file.path:
                        self._scan_result.files[i] = updated

    # ── Apply ─────────────────────────────────────────────────────────────────

    def _on_apply_all(self) -> None:
        if self._scan_result is None:
            return
        tasks = [
            (f.path, f.chosen_date)
            for f in self._scan_result.files
            if f.status == "resolved_single" and f.chosen_date is not None
        ]
        self._start_write(tasks)

    def _on_apply_selected(self) -> None:
        if self._scan_result is None:
            return
        selected_rows = {
            self._table._proxy.mapToSource(idx).row()
            for idx in self._table.selectedIndexes()
        }
        tasks = []
        for row in selected_rows:
            file = self._table.source_model().file_at(row)
            if file and file.status == "resolved_single" and file.chosen_date:
                tasks.append((file.path, file.chosen_date))
        self._start_write(tasks)

    def _start_write(self, tasks: list) -> None:
        if not tasks:
            QMessageBox.information(self, "Nothing to Apply",
                                    "No files with resolved dates to write.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Write",
            f"Write dates to {len(tasks)} file(s)?\n\n"
            "ExifTool will create <filename>_original backups automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        et_path = SettingsDialog.exiftool_path()
        writer = ExifWriter(exiftool_path=et_path)
        worker = WriteWorker(writer, tasks)
        worker.signals.progress.connect(
            lambda cur, total: (
                self._progress_bar.setRange(0, total),
                self._progress_bar.setValue(cur),
                self._status_label.setText(f"Writing {cur}/{total}…"),
            )
        )
        worker.signals.finished.connect(self._on_write_complete)
        worker.signals.error.connect(self._on_write_error)

        self._apply_btn.setEnabled(False)
        self._progress_bar.setRange(0, len(tasks))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._thread_pool.start(worker)

    def _on_write_complete(self, results: list[WriteResult]) -> None:
        self._progress_bar.setVisible(False)
        self._apply_btn.setEnabled(True)

        success = sum(1 for r in results if r.success)
        failed = len(results) - success
        self._status_label.setText(
            f"Done: {success} written, {failed} failed"
        )
        if failed:
            failed_names = "\n".join(
                r.path.name for r in results if not r.success
            )
            QMessageBox.warning(
                self, "Write Errors",
                f"{failed} file(s) could not be updated:\n{failed_names}"
            )

    def _on_write_error(self, error: str) -> None:
        self._progress_bar.setVisible(False)
        self._apply_btn.setEnabled(True)
        QMessageBox.critical(self, "Write Error", error)

    # ── Settings ─────────────────────────────────────────────────────────────

    def _on_settings(self) -> None:
        SettingsDialog(parent=self).exec()
