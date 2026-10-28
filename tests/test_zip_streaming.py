from __future__ import annotations

import hashlib
import shutil
import tempfile
import tracemalloc
import unittest
import zipfile
from pathlib import Path

from macrofactor_bridge.ooxml import XlsxPackage, file_sha256, validate_copy_integrity


ROOT = Path(__file__).resolve().parents[1]
LARGE_PART = "custom/large-unrelated.bin"


def add_large_part(path: Path, size_mib: int = 16) -> None:
    """Generate a large unrelated payload without retaining it in Python memory."""
    info = zipfile.ZipInfo(LARGE_PART, date_time=(2026, 8, 3, 12, 30, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100640 << 16
    info.internal_attr = 1
    info.extra = b"\xfe\xca\x02\x00ok"
    info.comment = b"synthetic member metadata"
    with zipfile.ZipFile(path, "a") as archive:
        archive.comment = b"synthetic archive comment"
        with archive.open(info, "w") as member:
            for _ in range(size_mib):
                member.write(b"A" * (1024 * 1024))


class ZipStreamingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_workbook_copy_and_validation_bound_memory_and_preserve_parts(self):
        source = self.root / "source.xlsx"
        output = self.root / "output.xlsx"
        shutil.copyfile(ROOT / "tests/fixtures/coach-template.xlsx", source)
        add_large_part(source)
        source_digest = file_sha256(source)
        package = XlsxPackage(source)
        sheet = package.sheet_by_name("Training Block")

        tracemalloc.start()
        try:
            package.write_copy(output, sheet, {"J5": "200 x 8"})
            validation = validate_copy_integrity(source, output, sheet.path)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertLess(peak, 8 * 1024 * 1024, "Unchanged ZIP parts must use bounded buffers")
        self.assertTrue(validation["zip_members_identical"])
        self.assertEqual(validation["unrelated_members_changed"], [])
        self.assertEqual(file_sha256(source), source_digest)
        self.assertEqual(XlsxPackage(output).sheet_snapshot(sheet.name).cells["J5"].value, "200 x 8")
        with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
            self.assertEqual(before.comment, after.comment)
            self.assertEqual(before.namelist(), after.namelist())
            original, candidate = before.getinfo(LARGE_PART), after.getinfo(LARGE_PART)
            for attribute in ("date_time", "compress_type", "external_attr", "internal_attr", "extra", "comment"):
                with self.subTest(attribute=attribute):
                    self.assertEqual(getattr(original, attribute), getattr(candidate, attribute))
            with before.open(LARGE_PART) as first, after.open(LARGE_PART) as second:
                self.assertEqual(hashlib.file_digest(first, "sha256").digest(),
                                 hashlib.file_digest(second, "sha256").digest())

    def test_integrity_comparison_finds_late_difference_and_length_change(self):
        source, output = self.root / "source.xlsx", self.root / "output.xlsx"
        prefix = b"A" * (2 * 1024 * 1024)
        with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as before:
            before.writestr("allowed.xml", b"old")
            before.writestr("late.bin", prefix + b"X")
            before.writestr("short.bin", prefix)
            before.writestr("empty.bin", b"")
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as after:
            after.writestr("allowed.xml", b"new")
            after.writestr("late.bin", prefix + b"Y")
            after.writestr("short.bin", prefix + b"extra")
            after.writestr("empty.bin", b"")

        validation = validate_copy_integrity(source, output, "allowed.xml")

        self.assertTrue(validation["zip_members_identical"])
        self.assertEqual(validation["unrelated_members_changed"], ["late.bin", "short.bin"])
