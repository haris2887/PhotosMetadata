# Task Queue

## 🔴 In Progress
_(nothing currently in progress — handoff to Windows / VS Code)_

## 🟡 Ready to Start
- [ ] **Install & smoke-test on Windows**: run `scripts\setup.bat`, install ExifTool, launch `python src\main.py`
- [ ] **Wire DMY/MDY setting into FilenameParser**: `SettingsDialog.date_format_pref()` is saved but `FilenameParser` doesn't read it yet — ambiguous dates always use first valid parse
- [ ] **Write `tests/integration/test_exif_writer.py`**: needs a real JPEG in `tests/fixtures/` and ExifTool installed; mark with `@pytest.mark.requires_exiftool`
- [ ] **Add test fixtures**: place a small JPEG with EXIF date, one without, and a sample Google Takeout `.json` into `tests/fixtures/`
- [ ] **End-to-end test with real Google Takeout folder**: scan a real Takeout export, verify JSON matching, dates applied correctly

## ⚪ Backlog
- [ ] Filter/search bar above results table (show only missing / only conflicts)
- [ ] Export summary report — CSV of what was changed (path, old date, new date, source)
- [ ] Undo last write — rename `filename_original` back to `filename`
- [ ] Dark mode toggle
- [ ] App icon + macOS `.app` bundle / Windows `.exe` installer (PyInstaller)
- [ ] CI pipeline — GitHub Actions: run `pytest tests/unit/` on every push
- [ ] Settings: remember last-used directory between sessions

## ✅ Done
- [x] Project structure scaffolded
- [x] `pyproject.toml`, `requirements.txt`, `.gitignore`, `setup.sh/bat/ps1`
- [x] Data models: `DateSource`, `PhotoFile`, `WriteResult`, `ScanResult`
- [x] Core logic: `FileScanner`, `FilenameParser`, `GoogleJsonReader`, `DateResolver`
- [x] ExifTool integration: `ExifReader`, `ExifWriter`, `ExifToolChecker`, `ProcessingPipeline`
- [x] Full GUI: `MainWindow`, `ResultsTable`, `ConflictDialog`, workers, `SettingsDialog`
- [x] 86 unit + integration tests passing
- [x] Repo pushed to GitHub (public): https://github.com/haris2887/PhotosMetadata
- [x] Windows setup scripts fixed (requirements.txt install, non-fatal pip upgrade)
