"""Protected JSON report destinations shared by the CLI and desktop app."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def validate_report_path(
    path: str | None, *, reserved: tuple[str | None, ...] = ()
) -> Path | None:
    """Reject input/output aliases and any already occupied destination."""
    if not path:
        return None
    output = Path(path)
    resolved = output.resolve(strict=False)
    for reserved_path in reserved:
        if reserved_path and resolved == Path(reserved_path).resolve(strict=False):
            raise FileExistsError(f"Report path is reserved input or output: {output}")
    # Path.exists() is false for dangling symlinks, which must also be preserved.
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Report path already exists: {output}")
    return output


def write_report(
    path: str | None, report: Any, *, reserved: tuple[str | None, ...] = ()
) -> None:
    output = validate_report_path(path, reserved=reserved)
    if output is None:
        return
    # Serialize before creating the destination so a malformed report cannot
    # leave an empty file that looks like a completed review.
    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    validate_report_path(str(output), reserved=reserved)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    created = os.fstat(fd)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as report_file:
            report_file.write(payload)
    except BaseException:
        # Remove only the file created by this call. If another process replaced
        # the path, its file is left alone.
        try:
            current = output.stat(follow_symlinks=False)
            if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                output.unlink()
        except OSError:
            pass
        raise
