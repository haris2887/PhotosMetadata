from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow
from utils.logging_config import setup_logging


def create_app(argv: list[str]) -> QApplication:
    app = QApplication(argv)
    app.setApplicationName("PhotosMetadata")
    app.setOrganizationName("PhotosMetadata")
    return app


def main() -> int:
    log_dir = Path.home() / ".photosmetadata" / "logs"
    setup_logging(log_dir)

    app = create_app(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
