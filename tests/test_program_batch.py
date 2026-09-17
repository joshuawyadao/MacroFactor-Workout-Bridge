from __future__ import annotations

import json
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from macrofactor_bridge.cli import main
from macrofactor_bridge.config import ConfigError
from macrofactor_bridge.ooxml import WorkbookError, file_sha256
from macrofactor_bridge.program_batch import run_program_batch, consolidate_review, select_manual_imports
from macrofactor_bridge.program_output_audit import OutputAudit, inspect_import_contract
from macrofactor_bridge.program_service import generate_program
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import add_day_header, write_program_workbook, write_macrofactor_program_template


def write_batch_coach(path, sheets):
    """Combine entirely synthetic inline-string sheets without a spreadsheet dependency."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
    content = "http://schemas.openxmlformats.org/package/2006/content-types"
    with tempfile.TemporaryDirectory() as directory:
        parts, xml_sheets = None, []
        for i, (name, cells) in enumerate(sheets):
            one = Path(directory) / f"sheet-{i}.xlsx"
            header_rows = [reference[1:] for reference, value in cells.items()
                           if reference.startswith("C") and str(value).startswith("Day ")]
            merges = tuple(f"{start}{row}:{end}{row}" for row in header_rows
                           for start, end in (("J", "K"), ("L", "M")))
            write_program_workbook(one, sheet_name=name, cells=cells, merges=merges)
            with zipfile.ZipFile(one) as archive:
                if parts is None:
                    parts = {n: archive.read(n) for n in archive.namelist()}
                xml_sheets.append(archive.read("xl/worksheets/sheet1.xml"))
        workbook = ET.fromstring(parts["xl/workbook.xml"])
        sheet_container = workbook.find(f"{{{ns}}}sheets")
        sheet_container.clear()
        relationships = ET.Element(f"{{{pkg}}}Relationships")
        types = ET.fromstring(parts["[Content_Types].xml"])
        for i, ((name, _), xml) in enumerate(zip(sheets, xml_sheets), start=1):
            ET.SubElement(sheet_container, f"{{{ns}}}sheet", {"name": name, "sheetId": str(i), f"{{{rel}}}id": f"rId{i}"})
            ET.SubElement(relationships, f"{{{pkg}}}Relationship", {"Id": f"rId{i}", "Type": rel + "/worksheet", "Target": f"worksheets/sheet{i}.xml"})
            if i > 1:
                ET.SubElement(types, f"{{{content}}}Override", {"PartName": f"/xl/worksheets/sheet{i}.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"})
            parts[f"xl/worksheets/sheet{i}.xml"] = xml
        parts["xl/workbook.xml"] = ET.tostring(workbook)
        parts["xl/_rels/workbook.xml.rels"] = ET.tostring(relationships)
        parts["[Content_Types].xml"] = ET.tostring(types)
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in parts.items():
                archive.writestr(name, data)


class ProgramBatchTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.coach, self.template = self.root / "coach.xlsx", self.root / "template.xlsx"
        self.config, self.manifest = self.root / "config.json", self.root / "manifest.json"
        self.output = self.root / "batch"
        self.payload = {
            "program": {"prescription_source": "base", "sheet_order": "right_to_left",
                        "week_pair_layout": "plan_then_result", "preserve_coach_notes": True,
                        "allow_blank_targets": True, "resize_template_workouts": True,
                        "defaults": {"set_type": "standard"}},
            "exercises": [{"canonical": "Synthetic Alpha", "coach_aliases": ["Coach Alpha"]},
                          {"canonical": "Synthetic Beta", "coach_aliases": ["Coach Beta"]}],
        }
        self.config.write_text(json.dumps(self.payload))
        self.sheets = []
        for name in ("Newest", "Middle", "Oldest"):
            cells = {}
            add_day_header(cells, row=5, day="Day 1")
            exercise_row(cells, 7, name="Coach Alpha", week_one=None, week_two=None)
            exercise_row(cells, 8, name="Coach Beta", week_one=None, week_two=None)
            self.sheets.append((name, cells))
        write_batch_coach(self.coach, self.sheets)
        write_macrofactor_program_template(self.template)

    def run_batch(self, *, manifest=None, generate=True):
        if manifest is not None:
            self.manifest.write_text(json.dumps({"schema_version": 1, **manifest}))
        return run_program_batch(self.coach, self.config, self.template, self.output,
                                 manifest_path=self.manifest if manifest is not None else None, generate=generate)

    def test_batch_generates_in_chronology_with_one_representative_and_private_reports(self):
        before = [file_sha256(p) for p in (self.coach, self.template, self.config)]
        report = self.run_batch()
        self.assertEqual([r["sheet"] for r in report.results], ["Oldest", "Middle", "Newest"])
        self.assertEqual([r["status"] for r in report.results], ["generated"] * 3, report.to_dict())
        self.assertEqual([file_sha256(p) for p in (self.coach, self.template, self.config)], before)
        self.assertTrue(report.inputs_unchanged)
        self.assertEqual(len(report.manual_import_plan["selected"]), 1)
        self.assertEqual(report.manual_import_plan["selected"][0]["item"], "block-003")
        self.assertFalse(report.manual_import_verified)
        self.assertEqual(len(list(self.output.glob("*.xlsx"))), 3)
        self.assertTrue((self.output / "summary.json").is_file())
        for result in report.results:
            self.assertTrue(result["source_audit"]["passed"])
            self.assertTrue(result["output_audit"]["passed"])
            detail = json.loads(Path(result["report"]).read_text())
            self.assertFalse(detail["preview"]["manual_import_verified"])
            self.assertNotIn("COMPLETED-RESULT-SENTINEL", json.dumps(detail))

    def test_exact_composite_start_after_and_preview_only(self):
        report = self.run_batch(manifest={"start_after": {"sheet": "Oldest", "block": "block-1"}}, generate=False)
        self.assertEqual([r["sheet"] for r in report.results], ["Middle", "Newest"])
        self.assertEqual([r["status"] for r in report.results], ["ready", "ready"])
        self.assertFalse(list(self.output.glob("*.xlsx")))
        self.assertFalse(report.manual_import_plan["selected"])

    def test_blocked_middle_does_not_stop_newest_and_questions_are_retained(self):
        self.sheets[1][1]["E7"] = "New Unknown Movement"
        write_batch_coach(self.coach, self.sheets)
        report = self.run_batch()
        self.assertEqual([r["status"] for r in report.results], ["generated", "blocked", "generated"])
        self.assertFalse((self.output / "block-002.xlsx").exists())
        self.assertTrue(any(q["code"] == "unmatched_exercise" for q in report.review_items))

    def test_all_block_weeks_cannot_be_silently_shortened_to_day_intersection(self):
        cells = self.sheets[1][1]
        add_day_header(cells, row=12, day="Day 2", week_one="Week 2", week_two="Week 3")
        exercise_row(cells, 14, name="Coach Alpha", week_one=None, week_two=None)
        exercise_row(cells, 15, name="Coach Beta", week_one=None, week_two=None)
        write_batch_coach(self.coach, self.sheets)
        report = self.run_batch()
        self.assertEqual([r["status"] for r in report.results], ["generated", "blocked", "generated"])
        self.assertTrue(any(i["code"] == "source_audit_complete_week_coverage" for i in report.results[1]["issues"]))
        self.assertFalse((self.output / "block-002.xlsx").exists())

    def test_unscannable_newest_is_reported_not_silently_omitted(self):
        self.sheets[0] = ("Newest", {"A1": "Unknown layout requiring review"})
        write_batch_coach(self.coach, self.sheets)
        report = self.run_batch()
        self.assertEqual(report.results[-1]["status"], "blocked")
        self.assertEqual(report.results[-1]["issues"][0]["code"], "no_program_blocks")
        self.assertFalse(report.manual_import_plan["newest_ready"])

    def test_explicit_sheet_skip_is_visible(self):
        report = self.run_batch(manifest={"skip_sheets": [{"sheet": "Middle", "reason": "Reference only, reviewed"}]})
        self.assertEqual(report.results[1]["status"], "skipped")
        self.assertEqual(report.results[1]["reason"], "Reference only, reviewed")

    def test_block_configuration_is_isolated_from_shared_and_other_blocks(self):
        scoped = json.loads(json.dumps(self.payload))
        scoped["exercises"][0]["program_base_overrides"] = {"sets": {"expected": "3", "value": "2"}}
        (self.root / "scoped.json").write_text(json.dumps(scoped))
        report = self.run_batch(manifest={"block_configs": [{"sheet": "Middle", "block": "block-1", "config": "scoped.json"}]})
        counts = []
        for item in report.results:
            detail = json.loads(Path(item["report"]).read_text())
            counts.append(detail["preview"]["program"]["days"][0]["exercises"][0]["prescriptions"][0]["set_count"]["value"])
        self.assertEqual(counts, [3, 2, 3])
        self.assertEqual(json.loads(self.config.read_text()), self.payload)

    def test_shared_block_specific_policy_is_rejected_before_writes(self):
        self.payload["exercises"][0]["program_notes"] = ["Block-specific cue"]
        self.config.write_text(json.dumps(self.payload))
        with self.assertRaisesRegex(ConfigError, "Shared batch"):
            self.run_batch()
        self.assertFalse(self.output.exists())

    def test_invalid_scoped_config_blocks_only_that_item(self):
        (self.root / "bad.json").write_text("invalid")
        report = self.run_batch(manifest={"block_configs": [{"sheet": "Middle", "block": "block-1", "config": "bad.json"}]})
        self.assertEqual([r["status"] for r in report.results], ["generated", "blocked", "generated"])
        self.assertEqual(report.results[1]["issues"][0]["code"], "block_config_invalid")

    def test_generation_error_continues_and_does_not_publish_failed_output(self):
        def generate(report, template, output):
            if report.sheet == "Middle":
                raise WorkbookError("synthetic writer failure")
            return generate_program(report, template, output)
        with patch("macrofactor_bridge.program_batch.generate_program", side_effect=generate):
            report = self.run_batch()
        self.assertEqual([r["status"] for r in report.results], ["generated", "generation_failed", "generated"])
        self.assertFalse((self.output / "block-002.xlsx").exists())

    def test_failed_independent_output_audit_never_publishes_candidate(self):
        with patch("macrofactor_bridge.program_batch.audit_program_output", return_value=OutputAudit(False, ("mismatch",), 1)):
            report = self.run_batch()
        self.assertTrue(all(r["status"] == "generation_failed" for r in report.results))
        self.assertFalse(list(self.output.glob("*.xlsx")))
        self.assertFalse(list(self.output.glob(".validate-*")))

    def test_input_drift_stops_remaining_items_and_no_candidate_is_published(self):
        def mutate(report, template, output):
            result = generate_program(report, template, output)
            self.config.write_text(self.config.read_text() + " ")
            return result
        with patch("macrofactor_bridge.program_batch.generate_program", side_effect=mutate):
            report = self.run_batch()
        self.assertFalse(report.inputs_unchanged)
        self.assertEqual([r["status"] for r in report.results[1:]], ["not_run_input_changed"] * 2)
        self.assertFalse(list(self.output.glob("*.xlsx")))
        self.assertFalse(report.manual_import_plan["selected"])

    def test_late_input_drift_discards_earlier_validated_candidates(self):
        def mutate(report, template, output):
            result = generate_program(report, template, output)
            if report.sheet == "Middle":
                self.config.write_text(self.config.read_text() + " ")
            return result
        with patch("macrofactor_bridge.program_batch.generate_program", side_effect=mutate):
            report = self.run_batch()
        self.assertFalse(report.inputs_unchanged)
        self.assertEqual(report.results[0]["status"], "invalidated_input_change")
        self.assertIsNone(report.results[0]["output"])
        self.assertFalse(list(self.output.glob("*.xlsx")))
        self.assertFalse(list(self.output.glob(".pending-*")))
        self.assertFalse(report.manual_import_plan["selected"])

    def test_final_publication_failure_is_local_and_cleans_temporary_candidates(self):
        link = os.link
        def publish(source, target):
            if Path(target) == self.output / "block-002.xlsx":
                raise OSError("synthetic publication failure")
            return link(source, target)
        with patch("macrofactor_bridge.program_batch.os.link", side_effect=publish):
            report = self.run_batch()
        self.assertEqual([r["status"] for r in report.results], ["generated", "generation_failed", "generated"])
        self.assertFalse((self.output / "block-002.xlsx").exists())
        self.assertFalse(list(self.output.glob(".pending-*")))
        self.assertIsNone(report.results[1]["output"])

    def test_drift_during_publication_removes_only_new_run_links(self):
        link = os.link
        def publish(source, target):
            result = link(source, target)
            if Path(target) == self.output / "block-002.xlsx":
                self.config.write_text(self.config.read_text() + " ")
            return result
        with patch("macrofactor_bridge.program_batch.os.link", side_effect=publish):
            report = self.run_batch()
        self.assertFalse(report.inputs_unchanged)
        self.assertTrue(all(r["status"] == "invalidated_input_change" for r in report.results))
        self.assertFalse(list(self.output.glob("*.xlsx")))
        self.assertFalse(report.manual_import_plan["selected"])

    def test_malformed_worksheet_blocks_only_that_sheet(self):
        with zipfile.ZipFile(self.coach) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        parts["xl/worksheets/sheet2.xml"] = b"<invalid"
        with zipfile.ZipFile(self.coach, "w") as archive:
            for name, content in parts.items():
                archive.writestr(name, content)
        report = self.run_batch()
        self.assertEqual([r["status"] for r in report.results], ["generated", "blocked", "generated"])
        self.assertEqual(report.results[1]["issues"][0]["code"], "discovery_failed")

    def test_older_custom_identity_gets_manual_coverage_besides_newest(self):
        scoped = json.loads(json.dumps(self.payload))
        scoped["exercises"][0].update(canonical="Custom Synthetic Movement", macrofactor_custom=True)
        (self.root / "custom.json").write_text(json.dumps(scoped))
        report = self.run_batch(manifest={"block_configs": [{"sheet": "Oldest", "block": "block-1", "config": "custom.json"}]})
        self.assertEqual([r["status"] for r in report.results], ["generated"] * 3)
        self.assertEqual({s["item"] for s in report.manual_import_plan["selected"]}, {"block-001", "block-003"})
        self.assertTrue(report.results[0]["identity_review_keys"])
        self.assertFalse(report.results[1]["identity_review_keys"])
        self.assertTrue(any(q["code"] == "custom_macrofactor_exercise" for q in report.review_items))

    def test_prior_structure_alone_does_not_cover_unseen_block_only_identity(self):
        first = self.run_batch()
        previous = Path(first.results[0]["output"])
        self.output = self.root / "next-run"
        scoped = json.loads(json.dumps(self.payload))
        scoped["exercises"][0]["canonical"] = "Scoped Synthetic Movement"
        (self.root / "scoped.json").write_text(json.dumps(scoped))
        report = self.run_batch(manifest={
            "block_configs": [{"sheet": "Oldest", "block": "block-1", "config": "scoped.json"}],
            "manual_import_evidence": [{"output": str(previous), "sha256": file_sha256(previous), "confirmed": True}],
        })
        self.assertEqual({s["item"] for s in report.manual_import_plan["selected"]}, {"block-001", "block-003"})
        self.assertTrue(all(not r["manual_import_verified"] for r in report.results))

    def test_existing_run_and_symlink_are_refused_without_overwrite(self):
        self.output.mkdir()
        marker = self.output / "existing.txt"
        marker.write_text("untouched")
        with self.assertRaises(FileExistsError):
            self.run_batch()
        self.assertEqual(marker.read_text(), "untouched")
        link = self.root / "link"
        link.symlink_to(self.output)
        with self.assertRaises(FileExistsError):
            run_program_batch(self.coach, self.config, self.template, link)

    def test_prior_import_evidence_never_marks_new_outputs_verified(self):
        report = self.run_batch()
        previous = Path(report.results[0]["output"])
        self.output = self.root / "another-run"
        report = self.run_batch(manifest={"manual_import_evidence": [{"output": str(previous), "sha256": file_sha256(previous), "confirmed": True}]})
        self.assertEqual(len(report.manual_import_plan["selected"]), 1)
        self.assertEqual(report.manual_import_plan["selected"][0]["reason"], "newest selected program")
        self.assertTrue(all(not r["manual_import_verified"] for r in report.results))

    def test_tampered_evidence_fails_before_writes(self):
        with self.assertRaisesRegex(WorkbookError, "evidence hash"):
            self.run_batch(manifest={"manual_import_evidence": [{"output": "template.xlsx", "sha256": "0" * 64, "confirmed": True}]})
        self.assertFalse(self.output.exists())

    def test_invalid_manifest_and_unknown_start_fail_before_writes(self):
        for manifest in ({"unknown": True}, {"start_after": {"sheet": "Missing", "block": "block-1"}},
                         {"manual_import_evidence": [{"output": "template.xlsx", "sha256": "0" * 64, "confirmed": False}]}):
            with self.subTest(manifest=manifest), self.assertRaises((ConfigError, WorkbookError)):
                self.run_batch(manifest=manifest)
            self.assertFalse(self.output.exists())

    def test_reviewed_reference_boundary_is_scoped_and_stale_marker_blocks(self):
        report = self.run_batch(manifest={"reference_boundaries": [
            {"sheet": "Middle", "block": "block-1", "marker_text": "Reviewed synthetic footer"}]})
        self.assertEqual([r["status"] for r in report.results], ["generated", "blocked", "generated"])
        self.assertTrue(any(i["code"].startswith("source_audit_") for i in report.results[1]["issues"]))
        self.assertIsNone(report.results[0]["reference_boundary_marker"])
        self.assertEqual(report.results[1]["reference_boundary_marker"], "Reviewed synthetic footer")

    def test_reference_boundary_manifest_rejects_implicit_or_unknown_keys(self):
        for entry in ({"sheet": "Missing", "block": "block-1", "marker_text": "Heading"},
                      {"sheet": "Middle", "block": "block-1", "marker_text": ""},
                      {"sheet": "Middle", "block": "block-1", "marker_text": "Heading", "end_row": 8}):
            with self.subTest(entry=entry), self.assertRaises(ConfigError):
                self.run_batch(manifest={"reference_boundaries": [entry]})
            self.assertFalse(self.output.exists())

    def test_cli_exit_code_and_help_for_partial_run(self):
        self.sheets[1][1]["E7"] = "Unknown"
        write_batch_coach(self.coach, self.sheets)
        output = StringIO()
        with redirect_stdout(output):
            code = main(["program-batch", "--workbook", str(self.coach), "--config", str(self.config),
                         "--template", str(self.template), "--output-dir", str(self.output), "--generate"])
        self.assertEqual(code, 1)
        self.assertIn("Consolidated review items", output.getvalue())
        self.assertIn("do not mark any candidate manually imported", output.getvalue())

    def test_questions_dedupe_same_context_not_different_prescriptions(self):
        issue = {"severity": "blocking", "code": "unmatched_exercise", "message": "Choose exact name",
                 "exercise": "Coach", "raw_text": "Variation", "cell": "E7"}
        results = [{"id": str(i), "sheet": str(i), "block": "block-1", "issues": [dict(issue)],
                    "source_context": {"E7": {"variation": "Variation", "sets": sets}}}
                   for i, sets in enumerate(("2", "2", "3"))]
        questions = consolidate_review(results)
        self.assertEqual(len(questions), 2)
        self.assertEqual(len(questions[0]["occurrences"]), 2)

    def test_representative_selection_covers_features_but_not_other_families(self):
        def item(n, features, days=1):
            return {"id": str(n), "status": "generated", "output": f"{n}.xlsx",
                    "contract": {"family": {"days": days}, "features": features}}
        results = [item(1, ["standard"]), item(2, ["standard", "myo"]), item(3, ["standard"], 2)]
        plan = select_manual_imports(results, [])
        self.assertEqual({r["item"] for r in plan["selected"]}, {"2", "3"})
        self.assertFalse(plan["manual_import_verified"])

    def test_derivative_mapping_diagnostics_share_one_question_but_raw_issues_remain(self):
        issues = [
            {"severity": "blocking", "code": "unmatched_exercise", "message": "Choose name", "exercise": "Coach", "cell": "E7", "day": "Day 1"},
            {"severity": "blocking", "code": "unavailable_macrofactor_exercise", "message": "Unavailable", "exercise": "Coach", "cell": None, "day": "Day 1"},
            {"severity": "blocking", "code": "source_audit_mapping", "message": "Mapping absent", "exercise": None, "cell": "E7", "day": "Day 1"},
        ]
        item = {"id": "1", "sheet": "Synthetic", "block": "block-1", "issues": issues, "source_rows": [
            {"row": 7, "cell": "E7", "day": "Day 1", "exercise": "Coach", "context": {"variation": "Unknown"}, "identities": []}]}
        questions = consolidate_review([item])
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["source_context"], {"variation": "Unknown"})
        self.assertEqual(len(item["issues"]), 3)

    def test_different_scoped_custom_identities_do_not_merge_review_questions(self):
        issue = {"severity": "warning", "code": "custom_macrofactor_exercise", "message": "Check database", "exercise": "Coach", "cell": "E7", "day": "Day 1"}
        results = [{"id": str(i), "sheet": str(i), "block": "block-1", "issues": [issue], "source_rows": [
            {"row": 7, "cell": "E7", "day": "Day 1", "exercise": "Coach", "context": {"variation": "Same"}, "identities": [identity]}]}
            for i, identity in enumerate(("identity-a", "identity-b"))]
        self.assertEqual(len(consolidate_review(results)), 2)


if __name__ == "__main__":
    unittest.main()
