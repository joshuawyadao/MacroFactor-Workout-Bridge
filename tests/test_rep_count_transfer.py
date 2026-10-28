from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

from macrofactor_bridge.cli import main
from macrofactor_bridge.config import load_config
from macrofactor_bridge.importers import load_exercise_log
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.rep_counts import rep_count_entry, save_rep_counts
from macrofactor_bridge.service import apply_changes, build_preview


ROOT = Path(__file__).resolve().parents[1]
COACH = ROOT / 'tests/fixtures/coach-template.xlsx'
CONFIG = ROOT / 'config/exercises.example.json'


class RepCountTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.export = self.root / 'log.csv'
        self.counts = self.root / 'rep-counts.json'
        self.output = self.root / 'output.xlsx'
        self.config = load_config(CONFIG)
        self.export.write_text(
            'Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n'
            '2026-08-04,Day One,Tempo Back Squat,Standard Set,200,8\n'
            '2026-08-04,Day One,Tempo Back Squat,Standard Set,200,6.33\n'
            '2026-08-04,Day One,Hanging Straight Leg Raise,Standard Set,,10\n'
        )

    def preview(self):
        return build_preview(self.export, COACH, self.config, 'Training Block',
                             'Week 1', date(2026, 8, 3), date(2026, 8, 9),
                             rep_counts_path=self.counts)

    def confirm(self):
        entry = rep_count_entry(load_exercise_log(self.export)[1])
        entry.update(full_reps=5, partial_reps=4)
        save_rep_counts(self.counts, self.export, [entry],
                        expected_export_hash=file_sha256(self.export))

    def test_unconfirmed_fraction_withholds_whole_exercise_without_hiding_other_results(self):
        report = self.preview()
        self.assertEqual([(p.cell, p.value) for p in report.proposed_writes], [('J6', '0 x 10')])
        self.assertEqual(len(report.rep_count_sets), 3)
        self.assertTrue(any('confirmation' in p['reason'] for p in report.ambiguous_matches))
        self.assertEqual(report.empty_day_markers, [])
        self.assertEqual(report.rep_counts_path, str(self.counts))
        self.assertIsNone(report.preview_rep_counts_hash)

    def test_confirmation_flows_through_preview_apply_and_keeps_import_provenance(self):
        original_hash = file_sha256(self.export)
        self.confirm()
        report = self.preview()
        values = {p.cell: p.value for p in report.proposed_writes}
        self.assertEqual(values['J5'], '200 x 8, 5 full + 4 partials')
        self.assertEqual(report.ambiguous_matches, [])
        self.assertEqual(report.rep_count_sets[1]['exported_reps'], '6.33')
        self.assertEqual(report.rep_count_sets[1]['full_reps'], 5)
        self.assertEqual(report.preview_rep_counts_hash, file_sha256(self.counts))
        apply_changes(report, self.config, self.output)
        package = XlsxPackage(self.output)
        cells = package.sheet_snapshot(package.sheet_by_name('Training Block')).cells
        self.assertEqual(cells['J5'].value, values['J5'])
        self.assertEqual(report.validation['unrelated_members_changed'], [])
        self.assertEqual(file_sha256(self.export), original_hash)
        raw = load_exercise_log(self.export)[1]
        self.assertEqual(str(raw.reps), '6.33')
        self.assertIsNone(raw.full_reps)
        self.assertIsNone(raw.partial_reps)

    def test_integer_exports_can_also_receive_explicit_split_counts(self):
        entry = rep_count_entry(load_exercise_log(self.export)[2])
        entry.update(full_reps=9, partial_reps=3)
        save_rep_counts(self.counts, self.export, [entry])
        values = {p.cell: p.value for p in self.preview().proposed_writes}
        self.assertEqual(values['J6'], '0 x 9 full + 3 partials')

    def test_unconfirmed_superset_member_withholds_the_shared_cell_until_confirmed(self):
        self.export.write_text(
            'Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n'
            '2026-08-04,Day One,Cable Curl,Standard Set,50,6.33\n'
            '2026-08-04,Day One,Cable Pressdown,Standard Set,60,10\n'
        )
        report = self.preview()
        self.assertEqual(report.proposed_writes, [])
        self.assertEqual(report.empty_day_markers, [])
        entry = rep_count_entry(load_exercise_log(self.export)[0])
        entry.update(full_reps=5, partial_reps=4)
        save_rep_counts(self.counts, self.export, [entry])
        values = {p.cell: p.value for p in self.preview().proposed_writes}
        self.assertEqual(values['J9'], '50/60 x 5 full + 4 partials/10')

    def test_changed_or_deleted_confirmation_file_requires_fresh_preview(self):
        self.confirm()
        report = self.preview()
        content = self.counts.read_text()
        for replacement in (content + '\n', None):
            with self.subTest(replacement=replacement is not None):
                if replacement is None:
                    self.counts.unlink()
                else:
                    self.counts.write_text(replacement)
                with self.assertRaisesRegex(WorkbookError, 'confirmations changed'):
                    apply_changes(report, self.config, self.output)
                self.assertFalse(self.output.exists())
                self.counts.write_text(content)

    def test_new_confirmation_file_after_preview_requires_fresh_preview(self):
        report = self.preview()
        self.confirm()
        with self.assertRaisesRegex(WorkbookError, 'confirmations changed'):
            apply_changes(report, self.config, self.output)
        self.assertFalse(self.output.exists())

    def test_confirmation_change_during_candidate_write_prevents_publication(self):
        from unittest.mock import patch
        self.confirm()
        report = self.preview()
        original = XlsxPackage.write_copy
        def change_after_write(package, *args):
            original(package, *args)
            self.counts.write_text(self.counts.read_text() + '\n')
        with patch.object(XlsxPackage, 'write_copy', change_after_write):
            with self.assertRaisesRegex(WorkbookError, 'confirmations changed'):
                apply_changes(report, self.config, self.output)
        self.assertFalse(self.output.exists())

    def cli(self, command='preview', *extra):
        args = [command, '--export', str(self.export), '--workbook', str(COACH),
                '--config', str(CONFIG), '--sheet', 'Training Block', '--week', 'Week 1',
                '--from-date', '2026-08-03', '--to-date', '2026-08-09', *extra]
        if command == 'apply':
            args.extend(['--output', str(self.output)])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return main(args)

    def test_cli_reads_explicit_confirmations_and_emits_a_reviewable_report(self):
        self.confirm()
        path = self.root / 'preview.json'
        self.assertEqual(self.cli('preview', '--rep-counts', str(self.counts), '--report', str(path)), 0)
        payload = json.loads(path.read_text())
        self.assertEqual(payload['rep_count_sets'][1]['partial_reps'], 4)
        self.assertEqual(self.cli('apply', '--rep-counts', str(self.counts)), 0)
        self.assertTrue(self.output.exists())

    def test_cli_requires_an_existing_explicit_file_and_protects_it_from_reports(self):
        self.assertEqual(self.cli('preview', '--rep-counts', str(self.counts)), 2)
        self.assertFalse(self.counts.exists())
        self.confirm()
        digest = file_sha256(self.counts)
        self.assertEqual(self.cli('preview', '--rep-counts', str(self.counts), '--report', str(self.counts)), 2)
        self.assertEqual(file_sha256(self.counts), digest)


if __name__ == '__main__':
    unittest.main()
