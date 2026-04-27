from __future__ import annotations

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.exiftool_checker import check_exiftool

_ORG = "PhotosMetadata"
_APP = "PhotosMetadata"


def load_settings() -> QSettings:
    return QSettings(_ORG, _APP)


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(440)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        # ExifTool path
        et_row = QHBoxLayout()
        self._et_path = QLineEdit()
        self._et_path.setPlaceholderText("exiftool")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_exiftool)
        test_btn = QPushButton("Test")
        test_btn.clicked.connect(self._test_exiftool)
        et_row.addWidget(self._et_path)
        et_row.addWidget(browse_btn)
        et_row.addWidget(test_btn)
        form.addRow("ExifTool path:", et_row)

        self._et_status = QLabel("")
        form.addRow("", self._et_status)

        # Ambiguous date format preference
        self._date_format = QComboBox()
        self._date_format.addItems(["Ask me each time", "Day/Month/Year (DMY)", "Month/Day/Year (MDY)"])
        form.addRow("Ambiguous date format:", self._date_format)

        # Backup option
        self._create_backup = QCheckBox("Create _original backup files when writing dates")
        self._create_backup.setToolTip(
            "When enabled, ExifTool saves the original file as filename_original before\n"
            "writing. Disable this to save disk space — changes cannot be undone."
        )
        form.addRow("Backups:", self._create_backup)

        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _browse_exiftool(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select ExifTool binary")
        if path:
            self._et_path.setText(path)

    def _test_exiftool(self) -> None:
        path = self._et_path.text().strip() or "exiftool"
        ok, msg = check_exiftool(path)
        if ok:
            self._et_status.setText(f"✅ Found ExifTool {msg}")
            self._et_status.setStyleSheet("color: green;")
        else:
            self._et_status.setText(f"❌ {msg}")
            self._et_status.setStyleSheet("color: red;")

    def _load(self) -> None:
        s = load_settings()
        self._et_path.setText(s.value("exiftool_path", ""))
        self._date_format.setCurrentIndex(int(s.value("date_format_pref", 0)))
        self._create_backup.setChecked(s.value("create_backup", True, type=bool))

    def _save_and_accept(self) -> None:
        s = load_settings()
        s.setValue("exiftool_path", self._et_path.text().strip())
        s.setValue("date_format_pref", self._date_format.currentIndex())
        s.setValue("create_backup", self._create_backup.isChecked())
        self.accept()

    @staticmethod
    def exiftool_path() -> str:
        return load_settings().value("exiftool_path", "") or "exiftool"

    @staticmethod
    def date_format_pref() -> int:
        """0=ask, 1=DMY, 2=MDY"""
        return int(load_settings().value("date_format_pref", 0))

    @staticmethod
    def create_backup() -> bool:
        """True = create _original backup (default); False = overwrite in place."""
        return load_settings().value("create_backup", True, type=bool)
