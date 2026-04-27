class ExifToolNotFoundError(RuntimeError):
    """ExifTool binary not found at the configured path. Fatal at startup."""


class ExifToolProcessError(RuntimeError):
    """ExifTool subprocess returned a non-zero exit code. Contains stderr."""


class ScanPermissionError(PermissionError):
    """A directory or file could not be read due to permissions. Non-fatal."""


class JsonParseError(ValueError):
    """A Google Photos Takeout JSON file exists but is malformed. Non-fatal."""


class DateParseError(ValueError):
    """A date string could not be parsed to a valid datetime. Non-fatal."""
