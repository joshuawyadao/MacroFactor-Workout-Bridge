from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.formatting import format_sets, format_superset
from macrofactor_bridge.importers import load_exercise_log
from macrofactor_bridge.models import SetRecord
from macrofactor_bridge.ooxml import XlsxPackage
from macrofactor_bridge.service import apply_changes, build_preview

ROOT = Path(__file__).resolve().parents[1]
COACH = ROOT / 'tests/fixtures/coach-template.xlsx'
CONFIG = ROOT / 'config/exercises.example.json'
INVALID = ('NaN', 'sNaN', 'Infinity', '-Infinity')


class NumericTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.export = self.root / 'log.csv'
        self.config = load_config(CONFIG)

    def preview(self, rows, config=None):
        self.export.write_text('Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n' +
                               ''.join(f'2026-08-04,Day One,{name},Standard Set,{weight},{reps}\n'
                                       for name, weight, reps in rows))
        return build_preview(self.export, COACH, config or self.config, 'Training Block',
                             'Week 1', date(2026, 8, 3), date(2026, 8, 9))

    def test_nonfinite_transfer_fields_are_reviewable_and_never_written(self):
        for field in ('weight', 'reps'):
            for value in INVALID:
                with self.subTest(field=field, value=value):
                    weight, reps = (value, '5') if field == 'weight' else ('200', value)
                    report = self.preview([('Tempo Back Squat', weight, reps)])
                    self.assertEqual(report.proposed_writes, [])
                    self.assertEqual(report.empty_day_markers, [])
                    issue = next(item for item in report.skipped_rows if item.get('field') == field)
                    self.assertEqual(issue['row'], 2)
                    self.assertEqual(issue['value'], value)
                    self.assertIn('nonfinite', issue['reason'])
                    # Import provenance is retained for read-only history inspection.
                    raw = load_exercise_log(self.export)[0]
                    self.assertEqual(str(getattr(raw, field)), value)

    def test_invalid_set_blocks_its_whole_target_but_other_exercises_remain_writable(self):
        report = self.preview([('Tempo Back Squat', '200', '5'),
                               ('Tempo Back Squat', 'NaN', '5'),
                               ('Hanging Straight Leg Raise', '', '10')])
        self.assertEqual([(write.cell, write.value) for write in report.proposed_writes], [('J6', '0 x 10')])
        self.assertEqual(report.empty_day_markers, [])
        self.assertTrue(any(item.get('cell') == 'J5' for item in report.ambiguous_matches))
        output = self.root / 'reviewed.xlsx'
        apply_changes(report, self.config, output)
        package = XlsxPackage(output)
        cells = package.sheet_snapshot(package.sheet_by_name('Training Block')).cells
        self.assertTrue(cells['J5'].is_empty)
        self.assertEqual(cells['J6'].value, '0 x 10')

    def test_invalid_superset_member_blocks_the_shared_target(self):
        report = self.preview([('Cable Curl', '50', '10'), ('Cable Pressdown', '60', 'sNaN')])
        self.assertEqual(report.proposed_writes, [])
        self.assertTrue(any(item.get('cell') == 'J9' for item in report.ambiguous_matches))

    def test_nonfinite_multipliers_are_rejected_by_configuration(self):
        path = self.root / 'mapping.json'
        for value in INVALID:
            with self.subTest(value=value):
                payload = json.loads(CONFIG.read_text())
                payload['exercises'][0]['weight_multiplier'] = value
                path.write_text(json.dumps(payload))
                with self.assertRaisesRegex(ConfigError, 'finite'):
                    load_config(path)

    def test_programmatic_nonfinite_multiplier_is_a_review_outcome(self):
        rule = replace(self.config.rules[0], weight_multiplier=Decimal('NaN'))
        config = replace(self.config, rules=(rule, *self.config.rules[1:]), source_path=None)
        report = self.preview([('Tempo Back Squat', '200', '5')], config)
        self.assertEqual(report.proposed_writes, [])
        self.assertTrue(report.ambiguous_matches)

    def test_formatters_reject_nonfinite_values_before_decimal_operations(self):
        rule = self.config.rules[0]
        for value in INVALID:
            for field in ('weight', 'reps'):
                with self.subTest(value=value, field=field):
                    record = SetRecord(2, date(2026, 8, 4), 'Day One', rule.canonical,
                                       'Standard Set', Decimal('200'), Decimal('5'))
                    record = replace(record, **{field: Decimal(value)})
                    with self.assertRaisesRegex(ValueError, 'finite'):
                        format_sets([record], rule)
                    with self.assertRaisesRegex(ValueError, 'finite'):
                        format_superset([([record], rule)])
