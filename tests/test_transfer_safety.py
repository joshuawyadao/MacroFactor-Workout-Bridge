from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from macrofactor_bridge import service
from macrofactor_bridge.config import load_config
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage

ROOT = Path(__file__).resolve().parents[1]


class TransferSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.coach = self.root / 'coach.xlsx'
        self.export = self.root / 'export.csv'
        self.mapping = self.root / 'mapping.json'
        self.output = self.root / 'result.xlsx'
        shutil.copyfile(ROOT / 'tests/fixtures/coach-template.xlsx', self.coach)
        shutil.copyfile(ROOT / 'config/exercises.example.json', self.mapping)
        self.export.write_text('Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n'
                               '2026-08-04,Day One,Tempo Back Squat,Standard Set,200,5\n')
        self.config = load_config(self.mapping)

    def preview(self, config=None):
        return service.build_preview(self.export, self.coach, config or self.config,
                                     'Training Block', 'Week 1', date(2026, 8, 3), date(2026, 8, 9))

    def change_mapping(self):
        payload = json.loads(self.mapping.read_text())
        payload['exercises'][0]['weight_multiplier'] = '2'
        self.mapping.write_text(json.dumps(payload))

    def assert_rejected(self, report, config=None):
        with self.assertRaises(WorkbookError):
            service.apply_changes(report, config or self.config, self.output)
        self.assertFalse(self.output.exists())
        self.assertIsNone(report.output_file)
        self.assertEqual(report.validation, {})

    def test_unchanged_inputs_publish_validated_copy(self):
        report = self.preview()
        self.assertTrue(report.proposed_writes)
        service.apply_changes(report, self.config, self.output)
        self.assertTrue(self.output.is_file())
        self.assertEqual(report.source_hash_before, report.source_hash_after)
        self.assertTrue(report.validation['zip_members_identical'])
        self.assertEqual(report.validation['unrelated_members_changed'], [])

    def test_export_changed_after_preview_is_rejected(self):
        report = self.preview()
        self.export.write_text(self.export.read_text().replace('200,5', '300,5'))
        self.assert_rejected(report)

    def test_workbook_changed_after_preview_is_rejected(self):
        report = self.preview()
        with self.coach.open('ab') as stream:
            stream.write(b'changed workbook')
        self.assert_rejected(report)

    def test_changed_mapping_is_rejected_with_old_or_reloaded_config(self):
        report = self.preview()
        self.change_mapping()
        self.assert_rejected(report)
        self.assert_rejected(report, load_config(self.mapping))

    def test_changed_programmatic_config_is_rejected(self):
        report = self.preview()
        changed_rule = replace(self.config.rules[0], weight_multiplier=Decimal('2'))
        config = replace(self.config, rules=(changed_rule, *self.config.rules[1:]))
        self.assert_rejected(report, config)

    def test_in_memory_config_without_source_path_is_supported(self):
        config = replace(self.config, source_path=None)
        report = self.preview(config)
        self.assertIsNone(report.preview_config_path)
        service.apply_changes(report, config, self.output)
        self.assertTrue(self.output.is_file())

    def test_mapping_replaced_by_invalid_json_shape_requires_new_preview(self):
        report = self.preview()
        for payload in ([], {'workbook': []}, {'workbook': {'week_header_pattern': 42}}):
            with self.subTest(payload=payload):
                self.mapping.write_text(json.dumps(payload))
                self.assert_rejected(report)

    def test_drift_during_preview_is_rejected(self):
        for changed in ('export', 'workbook', 'mapping'):
            with self.subTest(changed=changed):
                self.config = load_config(self.mapping)
                original = service.load_exercise_log_with_diagnostics
                def read_and_change(path):
                    result = original(path)
                    if changed == 'export':
                        self.export.write_text(self.export.read_text() + '\n')
                    elif changed == 'workbook':
                        with self.coach.open('ab') as stream:
                            stream.write(b'changed')
                    else:
                        self.change_mapping()
                    return result
                with patch.object(service, 'load_exercise_log_with_diagnostics', read_and_change):
                    with self.assertRaises(WorkbookError):
                        self.preview()

    def test_failed_integrity_checks_leave_no_output(self):
        for validation in ({'unrelated_members_changed': ['docProps/core.xml'], 'zip_members_identical': True},
                           {'unrelated_members_changed': [], 'zip_members_identical': False}):
            with self.subTest(validation=validation):
                report = self.preview()
                before = set(self.root.iterdir())
                with patch.object(service, 'validate_copy_integrity', return_value=validation):
                    self.assert_rejected(report)
                self.assertEqual(set(self.root.iterdir()), before)

    def test_partial_write_failure_leaves_no_output_or_staging_files(self):
        report = self.preview()
        before = set(self.root.iterdir())
        def partial_write(package, destination, *args):
            Path(destination).write_bytes(b'partial workbook')
            raise WorkbookError('write failed')
        with patch.object(XlsxPackage, 'write_copy', partial_write):
            self.assert_rejected(report)
        self.assertEqual(set(self.root.iterdir()), before)

    def test_drift_after_staging_leaves_no_output(self):
        report = self.preview()
        original = XlsxPackage.write_copy
        def write_and_change(package, *args):
            original(package, *args)
            self.export.write_text(self.export.read_text() + '\n')
        with patch.object(XlsxPackage, 'write_copy', write_and_change):
            self.assert_rejected(report)

    def test_late_collision_preserves_competing_file(self):
        report = self.preview()
        original = os.link
        def collide(source, destination):
            Path(destination).write_bytes(b'other writer')
            return original(source, destination)
        with patch('macrofactor_bridge.service.os.link', collide):
            with self.assertRaisesRegex(WorkbookError, 'Output already exists'):
                service.apply_changes(report, self.config, self.output)
        self.assertEqual(self.output.read_bytes(), b'other writer')
        self.assertIsNone(report.output_file)

    def test_drift_after_publication_removes_only_own_output(self):
        for replace_output in (False, True):
            with self.subTest(replace_output=replace_output):
                report = self.preview()
                original = os.link
                def publish_and_change(source, destination):
                    original(source, destination)
                    if replace_output:
                        Path(destination).unlink()
                        Path(destination).write_bytes(b'other writer')
                    self.export.write_text(self.export.read_text() + '\n')
                with patch('macrofactor_bridge.service.os.link', publish_and_change):
                    with self.assertRaises(WorkbookError):
                        service.apply_changes(report, self.config, self.output)
                if replace_output:
                    self.assertEqual(self.output.read_bytes(), b'other writer')
                else:
                    self.assertFalse(self.output.exists())
                self.assertIsNone(report.output_file)

    def test_missing_preview_provenance_requires_new_preview(self):
        report = self.preview()
        report.preview_source_hash = None
        self.assert_rejected(report)

    def test_low_level_copy_refuses_late_destination_collision(self):
        package = XlsxPackage(self.coach)
        sheet = package.sheet_by_name('Training Block')
        original = XlsxPackage._updated_sheet_xml
        def prepare_then_collide(*args):
            changed_xml = original(*args)
            self.output.write_bytes(b'other writer')
            return changed_xml
        with patch.object(XlsxPackage, '_updated_sheet_xml', staticmethod(prepare_then_collide)):
            with self.assertRaises(FileExistsError):
                package.write_copy(self.output, sheet, {'J5': '200 x 5'})
        self.assertEqual(self.output.read_bytes(), b'other writer')
