from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from models.photo_file import DateSource, PhotoFile


class ConflictDialog(QDialog):
    """
    Interactive dialog for resolving date conflicts.
    Accepts a list of conflicting PhotoFile objects and iterates through them
    with Prev/Next navigation. The caller reads .chosen_dates after exec().
    """

    def __init__(self, files: list[PhotoFile], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._files = files
        self._index = 0
        # Maps file path → chosen datetime (None = skipped)
        self.chosen_dates: dict[Path, datetime | None] = {}

        self.setWindowTitle("Date Conflict Resolution")
        self.setMinimumWidth(520)
        self._build_ui()
        self._load_file(0)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # Header
        self._header = QLabel()
        self._header.setWordWrap(True)
        font = self._header.font()
        font.setBold(True)
        self._header.setFont(font)
        root.addWidget(self._header)

        # Body: thumbnail + radio options side by side
        body = QHBoxLayout()
        self._thumb = QLabel()
        self._thumb.setFixedSize(160, 160)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0;")
        self._thumb.setText("[no preview]")
        body.addWidget(self._thumb)

        options_layout = QVBoxLayout()
        self._radio_group = QButtonGroup(self)
        self._radio_layout = options_layout
        body.addLayout(options_layout)
        root.addLayout(body)

        # Manual date entry (initially hidden)
        manual_row = QHBoxLayout()
        self._manual_radio = QRadioButton("Enter manually:")
        self._manual_radio.toggled.connect(self._on_manual_toggled)
        self._radio_group.addButton(self._manual_radio)
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setEnabled(False)
        manual_row.addWidget(self._manual_radio)
        manual_row.addWidget(self._date_edit)
        manual_row.addStretch()
        root.addLayout(manual_row)

        # Navigation + action buttons
        nav = QHBoxLayout()
        self._prev_btn = QPushButton("← Previous")
        self._prev_btn.clicked.connect(self._on_prev)
        self._skip_btn = QPushButton("Skip")
        self._skip_btn.clicked.connect(self._on_skip)
        self._apply_btn = QPushButton("Apply →")
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self._on_apply)

        nav.addWidget(self._prev_btn)
        nav.addStretch()
        nav.addWidget(self._skip_btn)
        nav.addWidget(self._apply_btn)
        root.addLayout(nav)

        # Progress label
        self._progress_label = QLabel()
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._progress_label)

    def _load_file(self, index: int) -> None:
        self._index = index
        file = self._files[index]

        self._header.setText(f"Multiple date sources found for:\n{file.path.name}")
        self._progress_label.setText(f"File {index + 1} of {len(self._files)}")
        self._prev_btn.setEnabled(index > 0)
        self._apply_btn.setText("Apply →" if index < len(self._files) - 1 else "Apply & Finish")

        # Load thumbnail for photos
        self._load_thumb(file.path)

        # Rebuild radio options (clear old buttons except manual)
        for btn in self._radio_group.buttons():
            if btn is not self._manual_radio:
                self._radio_group.removeButton(btn)
                btn.setParent(None)  # type: ignore[arg-type]

        sources = file.alternate_sources
        first_btn: QRadioButton | None = None
        for source in sources:
            label = self._source_label(source)
            radio = QRadioButton(label)
            radio.setProperty("source", source)
            self._radio_group.addButton(radio)
            self._radio_layout.insertWidget(self._radio_layout.count() - 2, radio)
            if first_btn is None:
                first_btn = radio

        if first_btn:
            first_btn.setChecked(True)

        self._date_edit.setEnabled(False)

    def _source_label(self, source: DateSource) -> str:
        type_labels = {
            "exif": "EXIF Date",
            "filename": "Filename Date",
            "google_json": "Google JSON Date",
            "folder_path": "Folder Path Date",
        }
        label = type_labels.get(source.source_type, source.source_type)
        dt_str = source.date_value.strftime("%Y-%m-%d")
        return f"{label}  {dt_str}  (from: {source.raw_value})"

    def _load_thumb(self, path: Path) -> None:
        try:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    160, 160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._thumb.setPixmap(scaled)
                self._thumb.setText("")
                return
        except Exception:
            pass
        self._thumb.setPixmap(QPixmap())
        self._thumb.setText("[no preview]")

    def _on_manual_toggled(self, checked: bool) -> None:
        self._date_edit.setEnabled(checked)

    def _on_skip(self) -> None:
        self.chosen_dates[self._files[self._index].path] = None
        self._advance()

    def _on_apply(self) -> None:
        chosen = self._get_chosen_date()
        self.chosen_dates[self._files[self._index].path] = chosen
        self._advance()

    def _advance(self) -> None:
        if self._index < len(self._files) - 1:
            self._load_file(self._index + 1)
        else:
            self.accept()

    def _on_prev(self) -> None:
        if self._index > 0:
            self._load_file(self._index - 1)

    def _get_chosen_date(self) -> datetime | None:
        if self._manual_radio.isChecked():
            qd = self._date_edit.date()
            return datetime(qd.year(), qd.month(), qd.day())
        for btn in self._radio_group.buttons():
            if btn is self._manual_radio:
                continue
            if btn.isChecked():
                source: DateSource | None = btn.property("source")
                if source:
                    return source.date_value
        return None
