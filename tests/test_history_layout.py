from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from macrofactor_bridge.config import load_config
from macrofactor_bridge.history import (
    BlockAnnotation, DashboardAnnotations, HistoryError, WeekAnnotation,
    build_history_dashboard, load_dashboard_annotations, save_dashboard_annotations,
    update_block_annotation, update_week_annotation,
)
from macrofactor_bridge.history_layout import HistoryWeek, week_layout_payload
from macrofactor_bridge.ooxml import file_sha256
from macrofactor_bridge.workbook import discover_workbook
from tests.history_fixture import LAYOUT, irregular_workbook


ROOT = Path(__file__).resolve().parents[1]


class HistoryLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.coach = self.root / 'coach.xlsx'
        irregular_workbook(self.coach)
        self.export = self.root / 'history.csv'
        self.export.write_text(
            'Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n' + ''.join(
                f'{day},Day One,Tempo Back Squat,Standard Set,200,5\n'
                for day in ('2026-07-27', '2026-08-03', '2026-08-09',
                            '2026-08-17', '2026-08-23', '2026-08-24')
            ), encoding='utf-8',
        )
        self.config = load_config(ROOT / 'config/exercises.example.json')
        self.path = self.root / 'annotations.json'
        self.annotation = BlockAnnotation(
            start_date=date(2026, 8, 3), week_layout=LAYOUT,
            weeks={'Week 8': WeekAnnotation(reason='vacation')},
        )

    def dashboard(self, annotation=None):
        return build_history_dashboard(
            self.export, self.coach, self.config,
            DashboardAnnotations({'Training Block': annotation or self.annotation}),
        )

    def test_explicit_layout_excludes_history_and_maps_date_week_without_compressing_gaps(self):
        hashes = [file_sha256(p) for p in (self.coach, self.export)]
        original_discovery = discover_workbook(self.coach, self.config)
        dashboard = self.dashboard()
        block = next(b for b in dashboard.blocks if b.name == 'Training Block')
        self.assertEqual(block.week_labels, ('Week 10', 'Week 11', 'Week 12'))
        self.assertEqual((block.completed_results, block.programmed_results), (3, 9))
        self.assertEqual(block.annotated_week_count, 0)
        self.assertEqual((block.mapped_set_count, block.mapped_training_days), (4, 4))
        trends = {str(t.week_start): t for t in dashboard.trends_for('Tempo Back Squat')}
        self.assertEqual(trends['2026-08-03'].block_week, 'Week 10')
        self.assertNotIn('2026-08-10', trends)  # No invented workout or skip.
        self.assertEqual(trends['2026-08-17'].block_week, 'Week 12')
        self.assertIsNone(trends['2026-07-27'].block_week)
        self.assertIsNone(trends['2026-08-24'].block_week)
        self.assertEqual(original_discovery, discover_workbook(self.coach, self.config))
        self.assertEqual(hashes, [file_sha256(p) for p in (self.coach, self.export)])

    def test_explicit_order_overrides_numeric_sorting(self):
        layout = tuple(replace(w, label=label) for w, label in zip(LAYOUT, ('Week 3', 'Week 1', 'Week 2')))
        dashboard = self.dashboard(replace(self.annotation, week_layout=layout))
        block = next(b for b in dashboard.blocks if b.name == 'Training Block')
        self.assertEqual(block.week_labels, ('Week 3', 'Week 1', 'Week 2'))
        self.assertEqual(dashboard.trends_for('Tempo Back Squat')[1].block_week, 'Week 3')

    def test_unmerged_headers_read_adjacent_result_columns(self):
        irregular_workbook(self.coach, header_merges=())
        block = next(b for b in self.dashboard().blocks if b.name == 'Training Block')
        self.assertEqual((block.completed_results, block.programmed_results), (3, 9))

    def test_layout_can_supply_weeks_without_any_automatic_header_match(self):
        self.config = replace(self.config, week_header_pattern=r'Never a week header')
        self.assertTrue(all(not sheet.weeks for sheet in discover_workbook(self.coach, self.config)))
        block = next(b for b in self.dashboard().blocks if b.name == 'Training Block')
        self.assertEqual(block.week_labels, ('Week 10', 'Week 11', 'Week 12'))

    def test_repeated_headers_cannot_count_the_same_result_column_twice(self):
        irregular_workbook(self.coach, extra_cells={'I11': 'Repeated header'},
            header_merges=('I3:J4', 'I11:J12'))
        layout = (LAYOUT[0], HistoryWeek('Different label', 'I11', 'Repeated header'))
        with self.assertRaisesRegex(HistoryError, 'distinct valid result columns'):
            self.dashboard(replace(self.annotation, week_layout=layout))

    def test_layout_survives_block_and_week_edits_and_round_trip(self):
        annotations = DashboardAnnotations({'Training Block': self.annotation})
        annotations = update_block_annotation(annotations, 'Training Block',
            block_type='strength', start_date=date(2026, 8, 3), notes='Synthetic note')
        annotations = update_week_annotation(annotations, 'Training Block', 'Week 12',
            status='modified', reason='planned', affected_movements=(), notes='Synthetic context')
        save_dashboard_annotations(self.path, annotations)
        self.assertEqual(load_dashboard_annotations(self.path), annotations)
        self.assertEqual(annotations.blocks['Training Block'].week_layout, LAYOUT)
        self.assertEqual(json.loads(self.path.read_text())['schema_version'], 2)

    def test_legacy_annotations_and_discovery_remain_supported(self):
        annotations = DashboardAnnotations({'Training Block': BlockAnnotation(start_date=date(2026, 8, 3))})
        save_dashboard_annotations(self.path, annotations)
        self.assertEqual(json.loads(self.path.read_text())['schema_version'], 1)
        self.assertEqual(load_dashboard_annotations(self.path), annotations)
        block = next(b for b in self.dashboard(annotations.blocks['Training Block']).blocks if b.name == 'Training Block')
        self.assertEqual(block.week_labels, ('Week 8', 'Week 9', 'Week 10', 'Week 11'))

    def test_repeated_legacy_labels_preserve_original_discovery_order(self):
        irregular_workbook(self.coach, extra_cells={'U3': 'Week 10'})
        discovered = next(s for s in discover_workbook(self.coach, self.config) if s.name == 'Training Block')
        block = next(b for b in self.dashboard(BlockAnnotation()).blocks if b.name == 'Training Block')
        self.assertEqual(block.week_labels, tuple(w.label for w in discovered.weeks))

    def test_invalid_layout_files_are_rejected(self):
        first = week_layout_payload(LAYOUT)[0]
        invalid = [[], {}, [None], [first, first],
            [{**first, 'header_cell': 'I0'}], [{**first, 'header_cell': 'XFE3'}],
            [{**first, 'expected_header': ''}], [{**first, 'label': 12}],
            [{**first, 'extra': True}],
            [first, {**first, 'label': 'week 10', 'header_cell': 'K3'}],
        ]
        for value in invalid:
            with self.subTest(value=value):
                self.path.write_text(json.dumps({'schema_version': 2, 'blocks': {
                    'Training Block': {'week_layout': value}}}))
                with self.assertRaises(HistoryError):
                    load_dashboard_annotations(self.path)
        self.path.write_text(json.dumps({'schema_version': 1, 'blocks': {
            'Training Block': {'week_layout': [first]}}}))
        with self.assertRaisesRegex(HistoryError, 'schema_version 2'):
            load_dashboard_annotations(self.path)

    def test_stale_or_wrong_workbook_anchors_fail_closed(self):
        for entry in (
            HistoryWeek('Final', 'M3', 'A header from another workbook'),
            HistoryWeek('Final', 'O3', 'Missing'),
            HistoryWeek('Final', 'D3', 'Variation'),
        ):
            with self.subTest(entry=entry), self.assertRaises(HistoryError):
                self.dashboard(replace(self.annotation, week_layout=(entry,)))
        with self.assertRaisesRegex(HistoryError, 'missing'):
            build_history_dashboard(self.export, self.coach, self.config,
                DashboardAnnotations({'Missing Block': self.annotation}))


if __name__ == '__main__':
    unittest.main()
