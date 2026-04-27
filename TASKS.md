# Task Queue

## 🔴 In Progress
_(nothing currently in progress)_

## 🟡 Ready to Start
- [ ] Install dependencies in a Python 3.12 venv: `bash scripts/setup.sh`
- [ ] Install ExifTool: `brew install exiftool` (macOS)
- [ ] Write tests/integration/test_exif_writer.py (requires real JPEG fixture + ExifTool)
- [ ] Add a small real JPEG (with + without EXIF) to tests/fixtures/
- [ ] Smoke-test the GUI: `python src/main.py`
- [ ] Test end-to-end with a real Google Takeout folder

## ⚪ Backlog
- [ ] Export summary report (CSV of what was changed)
- [ ] Filter bar above the results table (show only missing / only conflicts)
- [ ] Undo last write (rename _original back)
- [ ] Dark mode toggle
- [ ] Settings: DMY/MDY ambiguity preference is saved but not yet wired into FilenameParser
- [ ] App icon + macOS .app bundle / Windows installer
- [ ] CI pipeline (GitHub Actions: pytest on push)

## ✅ Done
- [x] Project structure scaffolded
- [x] pyproject.toml, requirements.txt, setup.sh
- [x] Data models (DateSource, PhotoFile, ScanResult)
- [x] Core logic: scanner, filename_parser, json_reader, resolver
- [x] ExifTool integration: reader, writer, checker, pipeline
- [x] Full GUI: MainWindow, ResultsTable, ConflictDialog, Workers, SettingsDialog
- [x] 86 unit + integration tests passing
