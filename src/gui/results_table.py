from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHeaderView, QTableView, QWidget

from models.photo_file import PhotoFile
from models.scan_result import ScanResult
from utils.path_utils import get_relative_display_path

_COLUMNS = ["File", "Type", "Status", "EXIF Date", "Filename Date", "JSON Date", "Folder Date", "Chosen Date"]

_STATUS_LABELS = {
    "has_exif":          "✅ Has EXIF",
    "missing":           "❌ Missing",
    "resolved_single":   "⚠️  Auto",
    "resolved_conflict": "⚠️  Conflict",
}

_STATUS_COLORS = {
    "has_exif":          QColor("#2e7d32"),
    "missing":           QColor("#c62828"),
    "resolved_single":   QColor("#e65100"),
    "resolved_conflict": QColor("#6a1b9a"),
}


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


class ResultsTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._files: list[PhotoFile] = []
        self._root: Path = Path("/")

    def update(self, result: ScanResult) -> None:
        self.beginResetModel()
        self._files = result.files
        self._root = result.root_dir
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._files)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._files):
            return None

        file = self._files[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return get_relative_display_path(file.path, self._root)
            if col == 1:
                return file.file_type.capitalize()
            if col == 2:
                return _STATUS_LABELS.get(file.status, file.status)
            if col == 3:
                return _fmt_dt(file.exif_date)
            if col == 4:
                return _fmt_dt(file.filename_date.date_value if file.filename_date else None)
            if col == 5:
                return _fmt_dt(file.json_date.date_value if file.json_date else None)
            if col == 6:
                return _fmt_dt(file.folder_date.date_value if file.folder_date else None)
            if col == 7:
                return _fmt_dt(file.chosen_date)

        if role == Qt.ItemDataRole.ForegroundRole and col == 2:
            return _STATUS_COLORS.get(file.status)

        if role == Qt.ItemDataRole.ToolTipRole and col == 0 and file.error:
            return f"Error: {file.error}"

        # Store the raw PhotoFile for access from other widgets
        if role == Qt.ItemDataRole.UserRole:
            return file

        return None

    def file_at(self, row: int) -> PhotoFile | None:
        if 0 <= row < len(self._files):
            return self._files[row]
        return None

    def update_file(self, path: Path, updated: PhotoFile) -> None:
        for i, f in enumerate(self._files):
            if f.path == path:
                self._files[i] = updated
                top_left = self.index(i, 0)
                bottom_right = self.index(i, len(_COLUMNS) - 1)
                self.dataChanged.emit(top_left, bottom_right)
                return


class ResultsTableView(QTableView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._model = ResultsTableModel(self)
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

    def load_result(self, result: ScanResult) -> None:
        self._model.update(result)
        self.sortByColumn(2, Qt.SortOrder.AscendingOrder)

    def source_model(self) -> ResultsTableModel:
        return self._model
