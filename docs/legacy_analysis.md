# Legacy Codebase Analysis

## Summary
The `/legacy/` directory contains the original prototype code that was used as a reference
when designing the current application. The new codebase was written from scratch with a
clean architecture rather than porting the legacy code directly.

## Key Differences from Legacy

| Aspect | Legacy | Current |
|---|---|---|
| Structure | Monolithic — logic mixed with UI | Strict core / GUI separation |
| ExifTool access | Per-file subprocess calls | Persistent process via pyexiftool |
| Testing | No test coverage | 153 unit tests (all passing); integration tests require ExifTool |
| Date parsing | Single regex pass | 4-layer filename strategy + folder path extraction with confidence levels |
| JSON sidecars | Not supported | Full Takeout support; 4-stage sidecar discovery; `_DirCache` for O(1) lookups |
| Performance | Sequential per-file | Parallel enrichment via `ThreadPoolExecutor` (scales to multi-core) |
| Error handling | Silent failures | Typed exception hierarchy; WriteResult per file |
| GUI | — | PyQt6 with sortable table, conflict dialog, bulk resolve, "Move Missing…" |

## Why a Rewrite
- No test coverage made iteration risky
- `os.path` patterns replaced with `pathlib.Path` throughout
- Monolithic structure made adding features (JSON sidecar, conflict resolution) impractical
- New architecture is fully testable without ExifTool or a display

## Legacy Reference
The legacy code is kept read-only in `/legacy/` for reference. Do not modify it.
