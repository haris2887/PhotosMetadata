from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHeaderView, QTableView, QWidget

from models.backup_file import BackupFile, BackupResult

_COLUMNS = ["File", "Source Root", "Size (MB)", "Status", "Duplicate Of", "Hash"]

_STATUS_LABELS = {
    "pending":    "⏳ Pending",
    "unique":     "❌ Not Backed Up",
    "backed_up":  "✅ Backed Up",
    "duplicate":  "⚠️  Duplicate",
    "error":      "🔴 Error",
}

_STATUS_COLORS = {
    "pending":   QColor("#757575"),
    "unique":    QColor("#c62828"),
    "backed_up": QColor("#2e7d32"),
    "duplicate": QColor("#e65100"),
    "error":     QColor("#880000"),
}


class BackupTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._files: list[BackupFile] = []

    def load(self, result: BackupResult) -> None:
        self.beginResetModel()
        self._files = result.files
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._files = []
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._files)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return _COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._files):
            return None

        f = self._files[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(f.relative_path)
            if col == 1:
                return str(f.source_root)
            if col == 2:
                return f"{f.size_mb:.2f}"
            if col == 3:
                return _STATUS_LABELS.get(f.status, f.status)
            if col == 4:
                return str(f.duplicate_of.name) if f.duplicate_of else "—"
            if col == 5:
                return f.hash_value or f.hash_error or "—"

        if role == Qt.ItemDataRole.ForegroundRole and col == 3:
            return _STATUS_COLORS.get(f.status)

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == 0:
                return str(f.path)
            if col == 4 and f.duplicate_of:
                return str(f.duplicate_of)
            if col == 5 and f.hash_error:
                return f"Error: {f.hash_error}"

        if role == Qt.ItemDataRole.UserRole:
            return f

        return None

    def file_at(self, row: int) -> BackupFile | None:
        if 0 <= row < len(self._files):
            return self._files[row]
        return None

    def refresh_row(self, file: BackupFile) -> None:
        for i, f in enumerate(self._files):
            if f.path == file.path:
                top_left = self.index(i, 0)
                bottom_right = self.index(i, len(_COLUMNS) - 1)
                self.dataChanged.emit(top_left, bottom_right)
                return


class BackupTableView(QTableView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._model = BackupTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self.setModel(self._proxy)

        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    def load_result(self, result: BackupResult) -> None:
        self._model.load(result)
        self.sortByColumn(3, Qt.SortOrder.AscendingOrder)

    def clear(self) -> None:
        self._model.clear()

    def source_model(self) -> BackupTableModel:
        return self._model

    def selected_files(self) -> list[BackupFile]:
        source_rows = sorted({
            self._proxy.mapToSource(idx).row()
            for idx in self.selectedIndexes()
        })
        return [f for r in source_rows
                if (f := self._model.file_at(r)) is not None]
