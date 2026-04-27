# Legacy Codebase Analysis

## Summary
Document findings from reviewing the original source code in /legacy/.

## Structure
- [ ] Document original file layout
- [ ] Identify core modules and their responsibilities
- [ ] Note any external dependencies

## Pain Points
- Deprecated API usage (e.g., `os.path` patterns)
- No test coverage
- Monolithic structure — logic mixed with UI

## Reuse Candidates
- List any logic worth porting directly
- Note any data formats or file structures to preserve compatibility with
