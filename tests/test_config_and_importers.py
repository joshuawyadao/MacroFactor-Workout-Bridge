from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.importers import ImportError, load_exercise_log

from tests.helpers import duplicate_first_worksheet, rewrite_xlsx, transform_cell


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class ConfigValidationTests(unittest.TestCase):
    def write_config(self, directory: str, payload: object) -> Path:
        path = Path(directory) / "mapping.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    @staticmethod
    def valid_payload() -> dict[str, object]:
        return {
            "workbook": {
                "exercise_header_labels": ["Exercise"],
                "week_header_pattern": r"^week\s*\d+$",
            },
            "exercises": [
                {
                    "canonical": "Squat",
                    "source_aliases": ["Back Squat"],
                    "coach_aliases": ["Squat"],
                }
            ],
        }

    def test_rejects_unreadable_and_invalid_json_configurations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with self.assertRaisesRegex(ConfigError, "Could not read configuration"):
                load_config(missing)

            malformed = Path(directory) / "malformed.json"
            malformed.write_text("{not json", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "Could not read configuration"):
                load_config(malformed)

    def test_rejects_invalid_top_level_mapping_fields(self) -> None:
        cases = (
            ({"workbook": {"exercise_header_labels": "Exercise"}, "exercises": [{}]}, "list of strings"),
            ({"workbook": {"week_header_pattern": "["}, "exercises": [{}]}, "Invalid workbook.week_header_pattern"),
            ({"exercises": []}, "non-empty list"),
            ({"exercises": ["Squat"]}, "must be an object"),
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, (payload, message) in enumerate(cases):
                with self.subTest(message=message):
                    path = Path(directory) / f"mapping-{index}.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaisesRegex(ConfigError, message):
                        load_config(path)

    def test_rejects_invalid_exercise_rule_fields(self) -> None:
        cases = (
            ({"canonical": "", "coach_aliases": ["Squat"]}, "canonical name"),
            ({"canonical": "Squat", "source_aliases": "Squat", "coach_aliases": ["Squat"]}, "invalid source_aliases"),
            ({"canonical": "Squat", "coach_aliases": []}, "needs coach_aliases"),
            ({"canonical": "Squat", "coach_aliases": ["Squat"], "weight_multiplier": "heavy"}, "invalid weight_multiplier"),
            ({"canonical": "Squat", "coach_aliases": ["Squat"], "weight_multiplier": 0}, "must be positive"),
            ({"canonical": "Squat", "coach_aliases": ["Squat"], "weight_suffix": 2}, "must be a string"),
            ({"canonical": "Squat", "coach_aliases": ["Squat"], "superset_group": 1}, "must be a string"),
            ({"canonical": "Squat", "coach_aliases": ["Squat"], "superset_order": "first"}, "must be an integer"),
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, (rule, message) in enumerate(cases):
                with self.subTest(message=message):
                    payload = self.valid_payload()
                    payload["exercises"] = [rule]
                    path = Path(directory) / f"rule-{index}.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaisesRegex(ConfigError, message):
                        load_config(path)

    def test_rejects_duplicate_source_aliases_after_normalization(self) -> None:
        payload = self.valid_payload()
        payload["exercises"] = [
            {"canonical": "Back Squat", "coach_aliases": ["Squat"]},
            {
                "canonical": "Tempo Squat",
                "source_aliases": ["  BACK   SQUAT  "],
                "coach_aliases": ["Tempo Squat"],
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ConfigError, "Source alias"):
                load_config(self.write_config(directory, payload))

    def test_defaults_source_alias_to_the_canonical_name(self) -> None:
        payload = self.valid_payload()
        payload["exercises"] = [{"canonical": "Squat", "coach_aliases": ["Squat"]}]
        with tempfile.TemporaryDirectory() as directory:
            config = load_config(self.write_config(directory, payload))
        self.assertEqual(config.rules[0].source_aliases, ("Squat",))


class ExerciseLogImportTests(unittest.TestCase):
    def write_csv(self, directory: str, contents: str, name: str = "log.csv") -> Path:
        path = Path(directory) / name
        path.write_text(contents, encoding="utf-8")
        return path

    def test_rejects_unsupported_file_types_and_missing_csv_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            unsupported = self.write_csv(directory, "data", "log.txt")
            with self.assertRaisesRegex(ImportError, "must be .csv or .xlsx"):
                load_exercise_log(unsupported)

            missing = self.write_csv(directory, "Date,Exercise\n2026-08-03,Squat\n")
            with self.assertRaisesRegex(ImportError, "missing required columns"):
                load_exercise_log(missing)

    def test_rejects_invalid_numbers_and_dates(self) -> None:
        header = "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
        cases = (
            ("2026-08-03,Lower,Squat,Standard Set,heavy,8\n", "Invalid numeric value"),
            ("next Tuesday,Lower,Squat,Standard Set,100,8\n", "Unsupported workout date"),
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, (row, message) in enumerate(cases):
                with self.subTest(message=message):
                    path = self.write_csv(directory, header + row, f"invalid-{index}.csv")
                    with self.assertRaisesRegex(ImportError, message):
                        load_exercise_log(path)

    def test_accepts_supported_date_formats_blank_weight_and_decimal_reps(self) -> None:
        contents = (
            "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
            "08/03/2026,Lower,Squat,Standard Set,,8.5\n"
            "2026/08/04,Upper,Press,Standard Set,100,8\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            records = load_exercise_log(self.write_csv(directory, contents))
        self.assertEqual([record.workout_date for record in records], [date(2026, 8, 3), date(2026, 8, 4)])
        self.assertIsNone(records[0].weight)
        self.assertEqual(str(records[0].reps), "8.5")

    def test_accepts_excel_serial_dates_from_xlsx_exports(self) -> None:
        serial = (date(2026, 8, 3) - date(1899, 12, 30)).days
        with tempfile.TemporaryDirectory() as directory:
            workbook = rewrite_xlsx(
                FIXTURES / "macrofactor-log.xlsx",
                Path(directory) / "serial-date.xlsx",
                {
                    "xl/worksheets/sheet1.xml": transform_cell(
                        "A2", text=str(serial), cell_type="n"
                    )
                },
            )
            records = load_exercise_log(workbook)
        self.assertEqual(records[0].workout_date, date(2026, 8, 3))

    def test_rejects_xlsx_without_a_log_table_or_with_multiple_tables(self) -> None:
        with self.assertRaisesRegex(ImportError, "No worksheet contains"):
            load_exercise_log(FIXTURES / "coach-template.xlsx")

        with tempfile.TemporaryDirectory() as directory:
            duplicated = duplicate_first_worksheet(
                FIXTURES / "macrofactor-log.xlsx", Path(directory) / "duplicate.xlsx"
            )
            with self.assertRaisesRegex(ImportError, "Multiple MacroFactor log tables"):
                load_exercise_log(duplicated)


if __name__ == "__main__":
    unittest.main()
