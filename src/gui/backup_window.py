from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QThreadPool, QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.backup_pipeline import BackupPipeline
from gui.backup_table import BackupTableView
from gui.backup_worker import BackupWorker, CopyWorker
from models.backup_file import BackupResult, CopyResult

logger = logging.getLogger(__name__)

_WINFSP_URL = "https://github.com/winfsp/winfsp/releases"
_SSHFS_URL = "https://github.com/winfsp/sshfs-win/releases"

_STAGE_LABELS = {
    "discover_sources": "Discovering source files…",
    "hash_sources":     "Hashing source files…",
    "detect_duplicates": "Detecting duplicates…",
    "discover_dest":    "Scanning destination…",
    "hash_dest":        "Hashing destination files…",
    "compare":          "Comparing source vs destination…",
}


class BackupWindow(QWidget):
    """
    Self-contained widget for the Photo Backups tab.

    Owns its own progress bar and status label — fully independent from the
    Photo Organiser tab.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scan_result: BackupResult | None = None
        self._pipeline: BackupPipeline | None = None
        self._thread_pool = QThreadPool.globalInstance()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addWidget(self._build_sources_group())
        root.addWidget(self._build_dest_group())
        root.addLayout(self._build_action_bar())
        root.addWidget(self._build_table())
        root.addLayout(self._build_status_bar())

    # ── Sources ──────────────────────────────────────────────────────────

    def _build_sources_group(self) -> QGroupBox:
        box = QGroupBox("Source Directories")
        layout = QVBoxLayout(box)

        self._source_list = QListWidget()
        self._source_list.setMaximumHeight(120)
        layout.addWidget(self._source_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Source…")
        add_btn.clicked.connect(self._on_add_source)
        self._remove_src_btn = QPushButton("Remove Selected")
        self._remove_src_btn.clicked.connect(self._on_remove_source)
        self._remove_src_btn.setEnabled(False)
        self._source_list.itemSelectionChanged.connect(
            lambda: self._remove_src_btn.setEnabled(
                bool(self._source_list.selectedItems())
            )
        )
        btn_row.addWidget(add_btn)
        btn_row.addWidget(self._remove_src_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addWidget(self._build_ssh_help())
        return box

    def _build_ssh_help(self) -> QGroupBox:
        """Collapsed help section explaining how to mount SSH shares on Windows."""
        box = QGroupBox("▶  How to add an SSH / network source (Windows)")
        box.setCheckable(True)
        box.setChecked(False)  # collapsed by default

        inner = QVBoxLayout(box)
        inner.setContentsMargins(8, 4, 8, 4)

        text = QLabel(
            "To scan files on an SSH server, mount it as a local drive first:\n"
            "1. Install <b>WinFSP</b> (kernel filesystem driver)\n"
            "2. Install <b>SSHFS-Win</b> (uses WinFSP to mount SSH shares)\n"
            "3. In Windows Explorer → Map Network Drive, use the path:\n"
            "   <code>\\\\sshfs\\user@hostname\\remote\\path</code>\n"
            "4. Add the resulting drive letter or UNC path above."
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        inner.addWidget(text)

        link_row = QHBoxLayout()
        for label, url in [("WinFSP releases", _WINFSP_URL), ("SSHFS-Win releases", _SSHFS_URL)]:
            lbl = QLabel(f'<a href="{url}">{label}</a>')
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setOpenExternalLinks(False)
            lbl.linkActivated.connect(
                lambda _url=url: QDesktopServices.openUrl(QUrl(_url))
            )
            link_row.addWidget(lbl)
        link_row.addStretch()
        inner.addLayout(link_row)

        return box

    # ── Destination ───────────────────────────────────────────────────────

    def _build_dest_group(self) -> QGroupBox:
        box = QGroupBox("Backup Destination")
        layout = QHBoxLayout(box)
        self._dest_edit = QLineEdit()
        self._dest_edit.setPlaceholderText("Choose destination folder…")
        self._dest_edit.textChanged.connect(self._update_button_states)
        layout.addWidget(self._dest_edit, stretch=1)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._on_browse_dest)
        layout.addWidget(browse_btn)
        return box

    # ── Action bar ────────────────────────────────────────────────────────

    def _build_action_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self._scan_btn = QPushButton("Scan && Hash")
        self._scan_btn.setEnabled(False)
        self._scan_btn.setToolTip("Scan source and destination directories, hash all files")
        self._scan_btn.clicked.connect(self._on_scan_clicked)
        row.addWidget(self._scan_btn)

        self._rehash_btn = QPushButton("Force Re-Hash")
        self._rehash_btn.setEnabled(False)
        self._rehash_btn.setToolTip(
            "Clear all cached hashes and recompute from scratch"
        )
        self._rehash_btn.clicked.connect(self._on_force_rehash)
        row.addWidget(self._rehash_btn)

        row.addStretch()

        self._backup_btn = QToolButton()
        self._backup_btn.setText("Backup Unique Files ▾")
        self._backup_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._backup_btn.setEnabled(False)
        backup_menu = QMenu(self._backup_btn)
        backup_menu.addAction("Backup All Unique", self._on_backup_all)
        backup_menu.addAction("Backup Selected Rows", self._on_backup_selected)
        self._backup_btn.setMenu(backup_menu)
        self._backup_btn.clicked.connect(self._on_backup_all)
        row.addWidget(self._backup_btn)

        return row

    # ── Table ─────────────────────────────────────────────────────────────

    def _build_table(self) -> QWidget:
        self._table = BackupTableView()
        return self._table

    # ── Status bar ────────────────────────────────────────────────────────

    def _build_status_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._status_label = QLabel("Add sources and a destination to begin.")
        row.addWidget(self._status_label, stretch=1)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimumWidth(200)
        self._progress_bar.setMaximumWidth(300)
        self._progress_bar.setVisible(False)
        row.addWidget(self._progress_bar)
        return row

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    def _on_add_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Add Source Directory")
        if not path:
            return
        # Avoid duplicates in the list
        existing = [
            self._source_list.item(i).text()
            for i in range(self._source_list.count())
        ]
        if path not in existing:
            self._source_list.addItem(QListWidgetItem(path))
        self._update_button_states()

    def _on_remove_source(self) -> None:
        for item in self._source_list.selectedItems():
            self._source_list.takeItem(self._source_list.row(item))
        self._update_button_states()

    def _sources(self) -> list[Path]:
        return [
            Path(self._source_list.item(i).text())
            for i in range(self._source_list.count())
        ]

    # ------------------------------------------------------------------
    # Destination
    # ------------------------------------------------------------------

    def _on_browse_dest(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose Backup Destination")
        if path:
            self._dest_edit.setText(path)

    def _destination(self) -> Path | None:
        text = self._dest_edit.text().strip()
        return Path(text) if text else None

    # ------------------------------------------------------------------
    # Button states
    # ------------------------------------------------------------------

    def _update_button_states(self) -> None:
        ready = bool(self._sources()) and bool(self._destination())
        self._scan_btn.setEnabled(ready)
        self._rehash_btn.setEnabled(ready)
        has_unique = self._scan_result is not None and bool(self._scan_result.unique)
        self._backup_btn.setEnabled(has_unique)

    # ------------------------------------------------------------------
    # Scan & hash
    # ------------------------------------------------------------------

    def _on_scan_clicked(self) -> None:
        self._start_scan(force_rehash=False)

    def _on_force_rehash(self) -> None:
        reply = QMessageBox.question(
            self,
            "Force Re-Hash",
            "This will delete all cached hashes and recompute every file from scratch.\n\n"
            "This may take a while for large libraries. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_scan(force_rehash=True)

    def _start_scan(self, force_rehash: bool) -> None:
        sources = self._sources()
        dest = self._destination()
        if not sources or dest is None:
            return

        self._pipeline = BackupPipeline.create()
        self._scan_result = None
        self._table.clear()
        self._backup_btn.setEnabled(False)
        self._scan_btn.setEnabled(False)
        self._rehash_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("Starting…")

        worker = BackupWorker(
            self._pipeline, sources, dest, force_rehash=force_rehash
        )
        worker.signals.progress.connect(self._on_scan_progress)
        worker.signals.finished.connect(self._on_scan_complete)
        worker.signals.error.connect(self._on_scan_error)
        self._thread_pool.start(worker)

    def _on_scan_progress(self, stage: str, current: int, total: int, name: str) -> None:
        label = _STAGE_LABELS.get(stage, stage)
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
            self._status_label.setText(
                f"{label}  {current:,} / {total:,}"
                + (f"  —  {name}" if name else "")
            )
        else:
            self._progress_bar.setRange(0, 0)
            self._status_label.setText(label)

    def _on_scan_complete(self, result: BackupResult) -> None:
        self._scan_result = result
        self._progress_bar.setVisible(False)
        self._table.load_result(result)
        self._update_button_states()
        self._scan_btn.setEnabled(True)
        self._rehash_btn.setEnabled(True)

        total = result.total
        unique = len(result.unique)
        backed = len(result.backed_up)
        dups = len(result.duplicates)
        errors = len(result.errors)
        self._status_label.setText(
            f"{total} files  |  "
            f"{unique} ❌ not backed up  |  "
            f"{backed} ✅ backed up  |  "
            f"{dups} ⚠️ duplicates"
            + (f"  |  {errors} errors" if errors else "")
        )

    def _on_scan_error(self, error: str) -> None:
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._rehash_btn.setEnabled(True)
        self._status_label.setText(f"Error: {error}")
        QMessageBox.critical(self, "Scan Error", error)

    # ------------------------------------------------------------------
    # Copy / backup
    # ------------------------------------------------------------------

    def _on_backup_all(self) -> None:
        if self._scan_result is None or not self._scan_result.unique:
            return
        self._start_copy(self._scan_result.unique)

    def _on_backup_selected(self) -> None:
        files = [
            f for f in self._table.selected_files() if f.status == "unique"
        ]
        if not files:
            QMessageBox.information(
                self,
                "No Unique Files Selected",
                "Select one or more rows with status 'Not Backed Up' first.",
            )
            return
        self._start_copy(files)

    def _start_copy(self, files: list) -> None:
        if self._pipeline is None or self._scan_result is None:
            return

        count = len(files)
        reply = QMessageBox.question(
            self,
            "Confirm Backup",
            f"Copy {count} file(s) to:\n{self._scan_result.destination}\n\n"
            "Folder structure will be preserved. Files already in the destination "
            "will not be overwritten.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._backup_btn.setEnabled(False)
        self._scan_btn.setEnabled(False)
        self._progress_bar.setRange(0, count)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText(f"Copying 0 / {count}…")

        worker = CopyWorker(self._pipeline, self._scan_result, files=files)
        worker.signals.progress.connect(
            lambda cur, total, name: (
                self._progress_bar.setValue(cur),
                self._status_label.setText(f"Copying {cur} / {total}  —  {name}"),
            )
        )
        worker.signals.finished.connect(self._on_copy_complete)
        worker.signals.error.connect(self._on_copy_error)
        self._thread_pool.start(worker)

    def _on_copy_complete(self, results: list[CopyResult]) -> None:
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._update_button_states()

        success = sum(1 for r in results if r.success)
        failed = [r for r in results if not r.success]

        # Refresh table to show updated copy_result state
        self._table.source_model().beginResetModel()
        self._table.source_model().endResetModel()

        self._status_label.setText(
            f"Backup complete: {success} copied"
            + (f", {len(failed)} failed" if failed else "")
        )

        if failed:
            names = "\n".join(r.source_path.name for r in failed[:20])
            QMessageBox.warning(
                self,
                "Copy Errors",
                f"{len(failed)} file(s) could not be copied:\n\n{names}",
            )

    def _on_copy_error(self, error: str) -> None:
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._update_button_states()
        QMessageBox.critical(self, "Copy Error", error)
