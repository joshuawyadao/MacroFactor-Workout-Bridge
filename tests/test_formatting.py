from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from macrofactor_bridge.formatting import format_sets, format_superset
from macrofactor_bridge.models import ExerciseRule, SetRecord


def record(set_type: str, weight: str | None, reps: str, row: int) -> SetRecord:
    return SetRecord(
        source_row=row,
        workout_date=date(2026, 8, 3),
        workout="Anonymized workout",
        exercise="Exercise",
        set_type=set_type,
        weight=Decimal(weight) if weight is not None else None,
        reps=Decimal(reps),
    )


class FormattingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rule = ExerciseRule(
            canonical="Exercise",
            source_aliases=("Exercise",),
            coach_aliases=("Exercise",),
        )

    def test_standard_sets_group_reps_and_separate_weight_changes(self) -> None:
        value = format_sets(
            [
                record("Standard Set", "200", "8", 1),
                record("Standard Set", "200", "7", 2),
                record("Standard Set", "180", "10", 3),
            ],
            self.rule,
        )
        self.assertEqual(value, "200 x 8, 7; 180 x 10")

    def test_bodyweight_is_zero(self) -> None:
        self.assertEqual(format_sets([record("Standard Set", None, "10", 1)], self.rule), "0 x 10")

    def test_bodyweight_does_not_receive_a_configured_suffix(self) -> None:
        suffixed = ExerciseRule(
            canonical="Bodyweight",
            source_aliases=("Bodyweight",),
            coach_aliases=("Bodyweight",),
            weight_suffix="s",
        )
        self.assertEqual(format_sets([record("Standard Set", None, "10", 1)], suffixed), "0 x 10")

    def test_myo_and_mini_sets_use_plus(self) -> None:
        value = format_sets(
            [
                record("Myo Set", "160", "10", 1),
                record("Mini-set", "160", "3", 2),
                record("Mini-set", "160", "2", 3),
            ],
            self.rule,
        )
        self.assertEqual(value, "160 x 10+3+2")

    def test_same_weight_standard_after_myo_series_uses_one_weight(self) -> None:
        value = format_sets(
            [
                record("Myo Set", "160", "10", 1),
                record("Mini-set", "160", "3", 2),
                record("Standard Set", "160", "8", 3),
            ],
            self.rule,
        )
        self.assertEqual(value, "160 x 10+3, 8")

    def test_same_weight_standard_and_myo_series_share_one_weight(self) -> None:
        value = format_sets(
            [
                record("Standard Set", "160", "12", 1),
                record("Myo Set", "160", "9", 2),
                record("Mini-set", "160", "3", 3),
                record("Myo Set", "160", "8", 4),
                record("Mini-set", "160", "4", 5),
            ],
            self.rule,
        )
        self.assertEqual(value, "160 x 12, 9+3, 8+4")

    def test_myo_series_with_new_weight_starts_new_group(self) -> None:
        value = format_sets(
            [
                record("Standard Set", "160", "12", 1),
                record("Myo Set", "140", "9", 2),
                record("Mini-set", "140", "3", 3),
                record("Standard Set", "140", "8", 4),
            ],
            self.rule,
        )
        self.assertEqual(value, "160 x 12; 140 x 9+3, 8")

    def test_changed_weight_mini_prevents_merging_next_anchor(self) -> None:
        value = format_sets(
            [
                record("Myo Set", "160", "10", 1),
                record("Mini-set", "140", "3", 2),
                record("Myo Set", "160", "8", 3),
            ],
            self.rule,
        )
        self.assertEqual(value, "160 x 10+140 x 3; 160 x 8")

    def test_changed_weight_mini_series_prints_new_load_once(self) -> None:
        value = format_sets(
            [
                record("Myo Set", "160", "10", 1),
                record("Mini-set", "140", "3", 2),
                record("Mini-set", "140", "2", 3),
            ],
            self.rule,
        )
        self.assertEqual(value, "160 x 10+140 x 3+2")

    def test_drop_sets_use_arrow(self) -> None:
        value = format_sets(
            [record("Standard Set", "100", "8", 1), record("Drop Set", "70", "10", 2)],
            self.rule,
        )
        self.assertEqual(value, "100 x 8→70 x 10")

    def test_drop_tail_prevents_merging_next_anchor(self) -> None:
        value = format_sets(
            [
                record("Standard Set", "100", "8", 1),
                record("Drop Set", "70", "10", 2),
                record("Standard Set", "100", "7", 3),
            ],
            self.rule,
        )
        self.assertEqual(value, "100 x 8→70 x 10; 100 x 7")

    def test_per_side_load_groups_reps_without_rounding_fractional_reps(self) -> None:
        converted = ExerciseRule(
            canonical="Lunge",
            source_aliases=("Lunge",),
            coach_aliases=("Lunge",),
            weight_multiplier=Decimal("0.5"),
            weight_suffix="s",
        )
        value = format_sets(
            [
                record("Standard Set", "90", "12.33", 1),
                record("Myo Set", "90", "8", 2),
                record("Mini-set", "90", "3", 3),
            ],
            converted,
        )
        self.assertEqual(value, "45s x 12.33, 8+3")

    def test_conversion_and_suffix_are_independent(self) -> None:
        converted = ExerciseRule(
            canonical="Lunge",
            source_aliases=("Lunge",),
            coach_aliases=("Lunge",),
            weight_multiplier=Decimal("0.5"),
            weight_suffix="s",
        )
        self.assertEqual(format_sets([record("Standard Set", "90", "12", 1)], converted), "45s x 12")
        suffix_only = ExerciseRule(
            canonical="Curl",
            source_aliases=("Curl",),
            coach_aliases=("Curl",),
            weight_suffix="s",
        )
        self.assertEqual(format_sets([record("Standard Set", "30", "12", 1)], suffix_only), "30s x 12")

    def test_superset_pairs_weights_and_reps_by_set_position(self) -> None:
        second_rule = ExerciseRule(
            canonical="Second",
            source_aliases=("Second",),
            coach_aliases=("Exercise",),
        )
        value = format_superset(
            [
                ([record("Standard Set", "55", "9", 1), record("Standard Set", "55", "9", 3)], self.rule),
                ([record("Standard Set", "65", "10", 2), record("Standard Set", "65", "9", 4)], second_rule),
            ]
        )
        self.assertEqual(value, "55/65 x 9/10, 9/9")

    def test_superset_separates_weight_pair_changes_with_semicolons(self) -> None:
        second_rule = ExerciseRule(
            canonical="Second",
            source_aliases=("Second",),
            coach_aliases=("Exercise",),
        )
        value = format_superset(
            [
                (
                    [
                        record("Standard Set", "55", "9", 1),
                        record("Standard Set", "55", "9", 3),
                        record("Standard Set", "55", "9", 5),
                    ],
                    self.rule,
                ),
                (
                    [
                        record("Standard Set", "65", "10", 2),
                        record("Standard Set", "55", "10", 4),
                        record("Standard Set", "65", "9", 6),
                    ],
                    second_rule,
                ),
            ]
        )
        self.assertEqual(value, "55/65 x 9/10; 55/55 x 9/10; 55/65 x 9/9")

    def test_superset_rejects_mismatched_completed_set_counts(self) -> None:
        with self.assertRaisesRegex(ValueError, "different completed-set counts"):
            format_superset(
                [
                    ([record("Standard Set", "55", "9", 1)], self.rule),
                    (
                        [record("Standard Set", "65", "10", 2), record("Standard Set", "65", "9", 4)],
                        self.rule,
                    ),
                ]
            )


if __name__ == "__main__":
    unittest.main()
