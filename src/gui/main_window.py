from __future__ import annotations

import logging
import shutil
from dataclasses import replace
from pathlib import Path

from datetime import datetime

from PyQt6.QtCore import QPoint, QThreadPool
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.exif_writer import ExifWriter
from core.exiftool_checker import check_exiftool
from core.pipeline import ProcessingPipeline
from gui.backup_window import BackupWindow
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
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)
        self._tabs.addTab(self._build_organiser_tab(), "Photo Organiser")
        self._tabs.addTab(BackupWindow(parent=self), "Photo Backups")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # ── Status bar ───────────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._status_label = QLabel("Ready")
        self._status_bar.addWidget(self._status_label, stretch=1)

        self._progress_count_label = QLabel("")
        self._progress_count_label.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress_count_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimumWidth(220)
        self._progress_bar.setMaximumWidth(300)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress_bar)

        self._root: Path | None = None

    def _on_tab_changed(self, index: int) -> None:
        self._status_label.setText("Ready")
        self._progress_bar.setVisible(False)
        self._progress_count_label.setVisible(False)

    def _build_organiser_tab(self) -> QWidget:
        """Return the Photo Organiser tab content (unchanged from original _build_ui)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
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

        self._move_missing_btn = QPushButton("Move Missing…")
        self._move_missing_btn.setEnabled(False)
        self._move_missing_btn.setToolTip(
            "Move files with no recoverable date to a separate folder"
        )
        self._move_missing_btn.clicked.connect(self._on_move_missing_clicked)
        toolbar.addWidget(self._move_missing_btn)

        self._move_selected_btn = QPushButton("Move Selected…")
        self._move_selected_btn.setEnabled(False)
        self._move_selected_btn.setToolTip(
            "Move the highlighted rows to a chosen folder"
        )
        self._move_selected_btn.clicked.connect(self._on_move_selected_clicked)
        toolbar.addWidget(self._move_selected_btn)

        settings_btn = QPushButton("⚙")
        settings_btn.setFixedWidth(32)
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self._on_settings)
        toolbar.addWidget(settings_btn)

        layout.addLayout(toolbar)

        # ── Results table ────────────────────────────────────────────────────
        self._table = ResultsTableView()
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
        layout.addWidget(self._table, stretch=1)

        return tab

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
            self._move_missing_btn.setEnabled(False)
            self._move_selected_btn.setEnabled(False)
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
        self._progress_bar.setRange(0, 0)  # indeterminate until total is known
        self._progress_bar.setFormat("")
        self._progress_bar.setVisible(True)
        self._progress_count_label.setText("Discovering files…")
        self._progress_count_label.setVisible(True)
        self._status_label.setText("Scanning…")

        _PREF_MAP = ("ask", "dmy", "mdy")
        date_pref = _PREF_MAP[SettingsDialog.date_format_pref()]
        pipeline = ProcessingPipeline.create(exiftool_path=et_path, date_pref=date_pref)
        worker = ScanWorker(pipeline, self._root)
        worker.signals.progress.connect(self._on_scan_progress)
        worker.signals.finished.connect(self._on_scan_complete)
        worker.signals.error.connect(self._on_scan_error)
        self._thread_pool.start(worker)

    def _on_scan_progress(self, current: int, total: int, name: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._progress_bar.setFormat("%p%")
        if current == 0:
            # EXIF batch read phase — total known but not yet counting per-file
            self._progress_count_label.setText(f"Reading EXIF  |  0 / {total:,} files")
            self._status_label.setText("Reading EXIF data…")
        else:
            self._progress_count_label.setText(f"{current:,} / {total:,} files")
            self._status_label.setText(f"Processing: {name}")

    def _on_scan_complete(self, result: ScanResult) -> None:
        self._scan_result = result
        self._progress_bar.setVisible(False)
        self._progress_count_label.setVisible(False)
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
        self._move_missing_btn.setEnabled(bool(result.missing))
        self._move_selected_btn.setEnabled(bool(result.files))

    def _on_scan_error(self, error: str) -> None:
        self._progress_bar.setVisible(False)
        self._progress_count_label.setVisible(False)
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
        tasks = [
            (f.path, f.chosen_date)
            for f in self._selected_files()
            if f.status == "resolved_single" and f.chosen_date is not None
        ]
        self._start_write(tasks)

    def _start_write(self, tasks: list) -> None:
        if not tasks:
            QMessageBox.information(self, "Nothing to Apply",
                                    "No files with resolved dates to write.")
            return

        create_backup = SettingsDialog.create_backup()
        backup_note = (
            "ExifTool will save originals as <filename>_original."
            if create_backup
            else "Backups are DISABLED — original files will be overwritten."
        )
        reply = QMessageBox.question(
            self,
            "Confirm Write",
            f"Write dates to {len(tasks)} file(s)?\n\n{backup_note}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        et_path = SettingsDialog.exiftool_path()
        writer = ExifWriter(exiftool_path=et_path, create_backup=create_backup)
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
        failed_results = [r for r in results if not r.success]
        failed = len(failed_results)

        self._status_label.setText(f"Done: {success} written, {failed} failed")

        if not failed_results:
            return

        failed_names = "\n".join(r.path.name for r in failed_results[:50])
        if failed > 50:
            failed_names += f"\n…and {failed - 50} more"

        reply = QMessageBox.question(
            self,
            "Write Errors",
            f"{failed} file(s) could not be updated:\n\n{failed_names}\n\n"
            f"Move these files to a '_unwritable' folder so they are easy to find?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._move_failed_files(failed_results)

    def _move_failed_files(self, failed_results: list[WriteResult]) -> None:
        if self._root is None:
            return

        from core.json_reader import GoogleJsonReader
        json_reader = GoogleJsonReader()

        dest_root = self._root / "_unwritable"
        moved = 0
        move_errors: list[str] = []

        for result in failed_results:
            try:
                # Preserve the relative subfolder structure under _unwritable/
                try:
                    rel = result.path.relative_to(self._root)
                except ValueError:
                    rel = Path(result.path.name)
                dest = dest_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)

                # Find JSON sidecar BEFORE moving the image (while paths still match)
                json_path = json_reader.find_json(result.path, scan_root=self._root)

                shutil.move(str(result.path), str(dest))
                moved += 1

                # Move the JSON sidecar to the same destination subfolder
                if json_path and json_path.exists():
                    try:
                        json_rel = json_path.relative_to(self._root)
                    except ValueError:
                        json_rel = Path(json_path.name)
                    json_dest = dest_root / json_rel
                    json_dest.parent.mkdir(parents=True, exist_ok=True)
                    if not json_dest.exists():
                        shutil.move(str(json_path), str(json_dest))
                        logger.info(
                            "Moved JSON sidecar %s → %s", json_path.name, json_dest.name
                        )
            except Exception as exc:
                move_errors.append(f"{result.path.name}: {exc}")

        msg = f"Moved {moved} file(s) to '{dest_root}'"
        if move_errors:
            msg += f" ({len(move_errors)} could not be moved)"
        self._status_label.setText(msg)

        if move_errors:
            QMessageBox.warning(
                self, "Move Errors",
                f"Could not move {len(move_errors)} file(s):\n\n"
                + "\n".join(move_errors[:20]),
            )

    def _on_write_error(self, error: str) -> None:
        self._progress_bar.setVisible(False)
        self._apply_btn.setEnabled(True)
        QMessageBox.critical(self, "Write Error", error)

    # ── Move missing files ────────────────────────────────────────────────────

    def _on_move_missing_clicked(self) -> None:
        if self._scan_result is None or self._root is None:
            return

        missing = self._scan_result.missing
        if not missing:
            QMessageBox.information(
                self, "No Missing Files",
                "There are no files with an unrecoverable date in the current scan."
            )
            return

        default_dest = str(self._root / "_undated")

        # ── Build dialog ──────────────────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle("Move Files With No Recoverable Date")
        dlg.setMinimumWidth(520)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        info = QLabel(
            f"<b>{len(missing)}</b> file(s) have no date that could be recovered "
            f"from the filename, a JSON sidecar, or existing EXIF data.\n\n"
            f"These files will be moved to the destination folder below, "
            f"preserving their relative subfolder structure."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        dest_row = QHBoxLayout()
        dest_edit = QLineEdit(default_dest)
        dest_row.addWidget(dest_edit, stretch=1)
        browse_btn = QPushButton("Browse…")

        def _browse() -> None:
            chosen = QFileDialog.getExistingDirectory(
                dlg, "Choose Destination Folder", dest_edit.text()
            )
            if chosen:
                dest_edit.setText(chosen)

        browse_btn.clicked.connect(_browse)
        dest_row.addWidget(browse_btn)
        form.addRow("Destination folder:", dest_row)
        layout.addLayout(form)

        move_json_cb = QCheckBox("Also move matching JSON sidecar files")
        move_json_cb.setChecked(True)
        layout.addWidget(move_json_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Move Files")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        dest_root = Path(dest_edit.text().strip())
        if not dest_root.name:
            QMessageBox.warning(self, "Invalid Path", "Please enter a destination folder.")
            return

        self._move_missing_files(missing, dest_root, move_json=move_json_cb.isChecked())

    def _move_missing_files(
        self,
        missing: list,
        dest_root: Path,
        move_json: bool,
    ) -> None:
        from core.json_reader import GoogleJsonReader
        json_reader = GoogleJsonReader()

        moved = 0
        json_moved = 0
        json_found_but_not_moved = 0
        move_errors: list[str] = []

        for file in missing:
            try:
                try:
                    rel = file.path.relative_to(self._root)
                except ValueError:
                    rel = Path(file.path.name)
                dest = dest_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)

                # Locate JSON before moving the image (path still valid)
                json_path = json_reader.find_json(file.path, scan_root=self._root)

                shutil.move(str(file.path), str(dest))
                moved += 1
                logger.info("Moved undated file %s → %s", file.path.name, dest)

                if json_path and json_path.exists():
                    if move_json:
                        try:
                            json_rel = json_path.relative_to(self._root)
                        except ValueError:
                            json_rel = Path(json_path.name)
                        json_dest = dest_root / json_rel
                        json_dest.parent.mkdir(parents=True, exist_ok=True)
                        if not json_dest.exists():
                            shutil.move(str(json_path), str(json_dest))
                            json_moved += 1
                            logger.info(
                                "Moved JSON sidecar %s → %s",
                                json_path.name, json_dest.name,
                            )
                    else:
                        json_found_but_not_moved += 1
                        logger.info(
                            "JSON sidecar left in place (not requested): %s",
                            json_path.name,
                        )
            except Exception as exc:
                move_errors.append(f"{file.path.name}: {exc}")

        # Update scan result so the table reflects files are gone
        if self._scan_result is not None:
            moved_paths = {f.path for f in missing if not any(
                e.startswith(f.path.name) for e in move_errors
            )}
            self._scan_result.files = [
                f for f in self._scan_result.files if f.path not in moved_paths
            ]
            self._table.load_result(self._scan_result)
            self._move_missing_btn.setEnabled(bool(self._scan_result.missing))

        parts = [f"Moved {moved} undated file(s) to '{dest_root.name}'"]
        if json_moved:
            parts.append(f"{json_moved} JSON sidecar(s) moved")
        if json_found_but_not_moved:
            parts.append(f"{json_found_but_not_moved} JSON sidecar(s) left in place")
        if move_errors:
            parts.append(f"{len(move_errors)} could not be moved")
        self._status_label.setText("  |  ".join(parts))

        if move_errors:
            QMessageBox.warning(
                self, "Move Errors",
                f"Could not move {len(move_errors)} file(s):\n\n"
                + "\n".join(move_errors[:20]),
            )

    # ── Move selected files ───────────────────────────────────────────────────

    def _on_move_selected_clicked(self) -> None:
        if self._scan_result is None or self._root is None:
            return

        files = self._selected_files()
        if not files:
            QMessageBox.information(
                self, "No Selection",
                "Select one or more rows in the table first."
            )
            return

        default_dest = str(self._root / "_moved")

        dlg = QDialog(self)
        dlg.setWindowTitle("Move Selected Files")
        dlg.setMinimumWidth(520)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        info = QLabel(
            f"<b>{len(files)}</b> file(s) selected.\n\n"
            f"These files will be moved to the destination folder below, "
            f"preserving their relative subfolder structure."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        dest_row = QHBoxLayout()
        dest_edit = QLineEdit(default_dest)
        dest_row.addWidget(dest_edit, stretch=1)
        browse_btn = QPushButton("Browse…")

        def _browse() -> None:
            chosen = QFileDialog.getExistingDirectory(
                dlg, "Choose Destination Folder", dest_edit.text()
            )
            if chosen:
                dest_edit.setText(chosen)

        browse_btn.clicked.connect(_browse)
        dest_row.addWidget(browse_btn)
        form.addRow("Destination folder:", dest_row)
        layout.addLayout(form)

        move_json_cb = QCheckBox("Also move matching JSON sidecar files")
        move_json_cb.setChecked(True)
        layout.addWidget(move_json_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Move Files")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        dest_root = Path(dest_edit.text().strip())
        if not dest_root.name:
            QMessageBox.warning(self, "Invalid Path", "Please enter a destination folder.")
            return

        self._move_files(files, dest_root, move_json=move_json_cb.isChecked())

    def _move_files(
        self,
        files: list[PhotoFile],
        dest_root: Path,
        move_json: bool,
    ) -> None:
        from core.json_reader import GoogleJsonReader
        json_reader = GoogleJsonReader()

        moved = 0
        json_moved = 0
        json_found_but_not_moved = 0
        move_errors: list[str] = []

        for file in files:
            try:
                try:
                    rel = file.path.relative_to(self._root)
                except ValueError:
                    rel = Path(file.path.name)
                dest = dest_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)

                json_path = json_reader.find_json(file.path, scan_root=self._root)

                shutil.move(str(file.path), str(dest))
                moved += 1
                logger.info("Moved selected file %s → %s", file.path.name, dest)

                if json_path and json_path.exists():
                    if move_json:
                        try:
                            json_rel = json_path.relative_to(self._root)
                        except ValueError:
                            json_rel = Path(json_path.name)
                        json_dest = dest_root / json_rel
                        json_dest.parent.mkdir(parents=True, exist_ok=True)
                        if not json_dest.exists():
                            shutil.move(str(json_path), str(json_dest))
                            json_moved += 1
                    else:
                        json_found_but_not_moved += 1
            except Exception as exc:
                move_errors.append(f"{file.path.name}: {exc}")

        # Remove moved files from the table
        if self._scan_result is not None:
            moved_paths = {f.path for f in files if not any(
                e.startswith(f.path.name) for e in move_errors
            )}
            self._scan_result.files = [
                f for f in self._scan_result.files if f.path not in moved_paths
            ]
            self._table.load_result(self._scan_result)
            self._move_missing_btn.setEnabled(bool(self._scan_result.missing))
            self._move_selected_btn.setEnabled(bool(self._scan_result.files))

        parts = [f"Moved {moved} file(s) to '{dest_root.name}'"]
        if json_moved:
            parts.append(f"{json_moved} JSON sidecar(s) moved")
        if json_found_but_not_moved:
            parts.append(f"{json_found_but_not_moved} JSON sidecar(s) left in place")
        if move_errors:
            parts.append(f"{len(move_errors)} could not be moved")
        self._status_label.setText("  |  ".join(parts))

        if move_errors:
            QMessageBox.warning(
                self, "Move Errors",
                f"Could not move {len(move_errors)} file(s):\n\n"
                + "\n".join(move_errors[:20]),
            )

    # ── Bulk resolve (right-click context menu) ───────────────────────────────

    def _on_table_context_menu(self, pos: QPoint) -> None:
        if self._scan_result is None:
            return

        # If nothing is selected, select the row under the cursor automatically.
        # (Qt's ExtendedSelection doesn't change selection on right-click alone.)
        if not self._table.selectedIndexes():
            idx = self._table.indexAt(pos)
            if idx.isValid():
                self._table.selectRow(idx.row())

        files = self._selected_files()
        if not files:
            return

        has_filename = any(f.filename_date for f in files)
        has_json = any(f.json_date for f in files)
        has_folder = any(f.folder_date for f in files)
        has_any = has_filename or has_json or has_folder

        menu = QMenu(self._table)
        menu.addSection(f"{len(files)} file{'s' if len(files) != 1 else ''} selected")

        act_fn = menu.addAction("Apply Filename Date to Selected")
        act_fn.setEnabled(has_filename)

        act_js = menu.addAction("Apply JSON Date to Selected")
        act_js.setEnabled(has_json)

        act_fd = menu.addAction("Apply Folder Date to Selected")
        act_fd.setEnabled(has_folder)

        menu.addSeparator()

        act_early = menu.addAction("Apply Earlier Date to Selected")
        act_early.setEnabled(has_any)

        act_late = menu.addAction("Apply Later Date to Selected")
        act_late.setEnabled(has_any)

        action = menu.exec(self._table.viewport().mapToGlobal(pos))

        if action == act_fn:
            self._bulk_apply("filename", files)
        elif action == act_js:
            self._bulk_apply("json", files)
        elif action == act_fd:
            self._bulk_apply("folder", files)
        elif action == act_early:
            self._bulk_apply("earlier", files)
        elif action == act_late:
            self._bulk_apply("later", files)

    def _selected_files(self) -> list[PhotoFile]:
        source_rows = sorted({
            self._table._proxy.mapToSource(idx).row()
            for idx in self._table.selectedIndexes()
        })
        return [f for r in source_rows
                if (f := self._table.source_model().file_at(r)) is not None]

    def _pick_date(self, file: PhotoFile, source: str) -> datetime | None:
        if source == "filename":
            return file.filename_date.date_value if file.filename_date else None
        if source == "json":
            return file.json_date.date_value if file.json_date else None
        if source == "folder":
            return file.folder_date.date_value if file.folder_date else None
        # "earlier" / "later" — consider all available sources
        candidates: list[datetime] = []
        if file.filename_date:
            candidates.append(file.filename_date.date_value)
        if file.json_date:
            candidates.append(file.json_date.date_value)
        if file.folder_date:
            candidates.append(file.folder_date.date_value)
        if file.exif_date:
            candidates.append(file.exif_date)
        if not candidates:
            return None
        return min(candidates) if source == "earlier" else max(candidates)

    def _bulk_apply(self, source: str, files: list[PhotoFile]) -> None:
        applied = 0
        skipped = 0

        for file in files:
            if file.status == "has_exif":
                skipped += 1
                continue
            dt = self._pick_date(file, source)
            if dt is None:
                skipped += 1
                continue

            updated = replace(file, chosen_date=dt, status="resolved_single")
            self._table.source_model().update_file(file.path, updated)

            if self._scan_result:
                for i, f in enumerate(self._scan_result.files):
                    if f.path == file.path:
                        self._scan_result.files[i] = updated
                        break

            applied += 1

        if self._scan_result:
            can_apply = any(
                f.status == "resolved_single" for f in self._scan_result.files
            )
            self._apply_btn.setEnabled(can_apply)

        labels = {
            "filename": "Filename Date",
            "json": "JSON Date",
            "folder": "Folder Date",
            "earlier": "Earlier Date",
            "later": "Later Date",
        }
        label = labels[source]
        if applied == 0:
            QMessageBox.information(
                self, "Nothing Applied",
                f"No selected files have a {label} available.\n"
                "Select files with a date in the relevant column first."
            )
            return

        msg = f"Applied {label} to {applied} file(s)."
        if skipped:
            msg += f"  ({skipped} skipped — source not available or already has EXIF.)"
        self._status_label.setText(msg)
        # Remind user to click Apply Dates to write the dates to disk
        if applied > 0:
            self._apply_btn.setEnabled(True)

    # ── Settings ─────────────────────────────────────────────────────────────

    def _on_settings(self) -> None:
        SettingsDialog(parent=self).exec()
