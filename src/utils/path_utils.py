from __future__ import annotations

from pathlib import Path


def get_relative_display_path(path: Path, root: Path) -> str:
    """Return path relative to root for display in the results table."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def safe_stem(path: Path) -> str:
    """
    Return the file stem with stacked extensions stripped.
    e.g. 'photo.jpg.json' → 'photo', 'IMG_001.jpg' → 'IMG_001'
    """
    name = path.name
    # Strip all extensions until a clean stem remains
    p = Path(name)
    while p.suffix:
        p = Path(p.stem)
    return p.name
