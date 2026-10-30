from __future__ import annotations

import unittest

from macrofactor_bridge.ooxml import XlsxPackage, file_sha256
from macrofactor_bridge.program_audit import audit_coach_program
from macrofactor_bridge.program_output_audit import audit_program_output
from macrofactor_bridge.program_service import generate_program
from tests import test_program_duration_defaults as default_fixtures


class NativeTimeRequirementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_fixtures.NativeDurationDefaultIntegrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.payload["program"]["allow_blank_targets"] = False
        self.fixture.payload["program"]["defaults"].pop("rep_min")
        self.fixture.payload["program"]["defaults"].pop("rep_max")

    def test_exact_native_timed_sets_resolve_only_missing_rep_blockers(self):
        fixture = self.fixture
        original = file_sha256(fixture.coach), file_sha256(fixture.template)
        config, block, report = fixture.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        self.assertFalse(any(issue.code == "missing_prescription_field" for issue in report.blocking_issues))
        timed = report.program.days[0].exercises[0].prescriptions[0]
        self.assertEqual([target.value for target in timed.set_duration_targets], [30, 30])
        self.assertEqual((timed.rep_min.value, timed.rep_max.value), (None, None))
        self.assertTrue(audit_coach_program(fixture.coach, config, block, report).passed)
        generate_program(report, fixture.template, fixture.output)
        cells = XlsxPackage(fixture.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["F4"].value, cells["K4"].value), (None, None))
        self.assertEqual((cells["I4"].value, cells["N4"].value), (30, 30))
        self.assertTrue(audit_program_output(report.program, fixture.output, fixture.template).passed)
        self.assertEqual((file_sha256(fixture.coach), file_sha256(fixture.template)), original)

    def test_unrelated_missing_reps_still_block(self):
        fixture = self.fixture
        fixture.cells["G7"] = None
        fixture.write_coach()
        _, _, report = fixture.preview()
        self.assertFalse(report.generation_safe)
        self.assertTrue(any(issue.code == "missing_prescription_field"
                            and issue.exercise == "Old Exercise 1-2" for issue in report.blocking_issues),
                        report.blocking_issues)
        self.assertFalse(any(issue.code == "missing_prescription_field"
                             and issue.exercise == "Old Exercise 1-1" for issue in report.blocking_issues),
                         report.blocking_issues)

    def test_duplicate_same_name_rows_cannot_hide_missing_reps(self):
        fixture = self.fixture
        fixture.cells["E7"] = "Old Exercise 1-1"
        fixture.cells["G7"] = None
        fixture.write_coach()
        _, _, report = fixture.preview()
        self.assertFalse(report.generation_safe)
        self.assertTrue(any(issue.code == "missing_prescription_field"
                            for issue in report.blocking_issues), report.blocking_issues)
        self.assertTrue(any(issue.code == "invalid_program_template"
                            for issue in report.blocking_issues), report.blocking_issues)

    def test_missing_rir_rest_and_set_type_keep_their_own_blockers(self):
        for missing in ("rir", "rest", "set_type"):
            with self.subTest(missing=missing):
                fixture = default_fixtures.NativeDurationDefaultIntegrationTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                fixture.payload["program"]["allow_blank_targets"] = False
                defaults = fixture.payload["program"]["defaults"]
                defaults.pop("rep_min")
                defaults.pop("rep_max")
                if missing == "rir":
                    defaults.pop("rir")
                elif missing == "rest":
                    defaults.pop("rest_seconds")
                    fixture.cells["H6"] = None
                else:
                    defaults.pop("set_type")
                    fixture.cells["D6"] = None
                fixture.write_coach()
                _, _, report = fixture.preview()
                self.assertFalse(report.generation_safe)
                expected = {"rir": "No supported RIR value was provided",
                            "rest": "No supported rest value was provided",
                            "set_type": "No supported set type value was provided"}[missing]
                self.assertTrue(any(issue.code == "missing_prescription_field" and issue.message == expected
                                    for issue in report.blocking_issues), report.blocking_issues)


if __name__ == "__main__":
    unittest.main()
