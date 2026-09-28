from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None

if HAS_QT:
    from PySide6.QtWidgets import QApplication, QFileDialog

    from macrofactor_bridge.desktop import BridgeWindow
    from tests.gui_support import dispose_widget

from macrofactor_bridge.models import BridgeReport
from macrofactor_bridge.reporting import validate_report_path, write_report


def report_for(root: Path) -> BridgeReport:
    report = BridgeReport(
        str(root / "export.xlsx"),
        str(root / "coach.xlsx"),
        "Training Block",
        "Week 1",
        "2026-08-03",
        "2026-08-09",
    )
    report.output_file = str(root / "generated.xlsx")
    report.__dict__["preview_config_path"] = str(root / "reviewed-mapping.json")
    return report


class ReportWriterTests(unittest.TestCase):
    def test_exclusive_create_preserves_a_late_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "review.json"
            report = report_for(root)
            validate_report_path(str(destination))
            real_open = os.open

            def race_open(path: os.PathLike[str], flags: int, mode: int = 0o777) -> int:
                destination.write_bytes(b"created by another writer")
                return real_open(path, flags, mode)

            with patch("macrofactor_bridge.reporting.os.open", side_effect=race_open):
                with self.assertRaises(FileExistsError):
                    write_report(str(destination), report)
            self.assertEqual(destination.read_bytes(), b"created by another writer")

    def test_serialization_failure_leaves_no_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "review.json"
            report = report_for(root)
            with patch.object(report, "to_dict", side_effect=TypeError("bad report")):
                with self.assertRaisesRegex(TypeError, "bad report"):
                    write_report(str(destination), report)
            self.assertFalse(destination.exists())

    def test_write_failure_removes_only_its_partial_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "review.json"
            report = report_for(root)
            real_fdopen = os.fdopen

            class FailingWriter:
                def __init__(self, fd: int, *args: object, **kwargs: object) -> None:
                    self.file = real_fdopen(fd, *args, **kwargs)

                def __enter__(self) -> "FailingWriter":
                    return self

                def __exit__(self, *args: object) -> None:
                    self.file.__exit__(*args)

                def write(self, payload: str) -> None:
                    self.file.write(payload[:10])
                    raise OSError("write failed")

            with patch("macrofactor_bridge.reporting.os.fdopen", FailingWriter):
                with self.assertRaisesRegex(OSError, "write failed"):
                    write_report(str(destination), report)
            self.assertFalse(destination.exists())


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class DesktopReportSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = report_for(self.root)
        self.window = BridgeWindow()
        self.addCleanup(dispose_widget, self.window)
        self.window.export_path.setText(self.report.input_export)
        self.window.workbook_path.setText(self.report.input_workbook)
        self.window.config_path.setText(str(self.root / "current-mapping.json"))
        self.window._report = self.report

    def _save_to(self, destination: Path) -> tuple[bool, str]:
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(destination), "")), \
             patch.object(self.window, "_show_error") as error:
            self.window._save_report()
        return error.called, str(error.call_args.args[1]) if error.called else ""

    def test_existing_report_is_preserved(self) -> None:
        destination = self.root / "report.json"
        destination.write_bytes(b"keep original report")

        failed, message = self._save_to(destination)

        self.assertTrue(failed)
        self.assertIn("already exists", message)
        self.assertEqual(destination.read_bytes(), b"keep original report")

    def test_current_and_reviewed_inputs_and_generated_workbook_are_reserved(self) -> None:
        protected = (
            Path(self.report.input_export),
            Path(self.report.input_workbook),
            self.root / "current-mapping.json",
            self.root / "reviewed-mapping.json",
            Path(self.report.output_file),
        )
        for destination in protected:
            with self.subTest(destination=destination.name):
                destination.write_bytes(b"keep protected input")
                failed, message = self._save_to(destination)
                self.assertTrue(failed)
                self.assertIn("reserved", message)
                self.assertEqual(destination.read_bytes(), b"keep protected input")

    def test_symlink_alias_and_dangling_symlink_are_rejected(self) -> None:
        source = Path(self.report.input_export)
        source.write_bytes(b"keep source")
        alias = self.root / "alias.json"
        alias.symlink_to(source)
        failed, message = self._save_to(alias)
        self.assertTrue(failed)
        self.assertIn("reserved", message)
        self.assertEqual(source.read_bytes(), b"keep source")

        dangling = self.root / "dangling.json"
        dangling.symlink_to(self.root / "missing.json")
        failed, message = self._save_to(dangling)
        self.assertTrue(failed)
        self.assertIn("already exists", message)
        self.assertTrue(dangling.is_symlink())

    def test_new_report_is_created_with_report_payload(self) -> None:
        destination = self.root / "reports" / "review.json"
        failed, _ = self._save_to(destination)
        self.assertFalse(failed)
        self.assertEqual(destination.read_text(encoding="utf-8")[-1], "\n")
        self.assertIn('"input_export"', destination.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
