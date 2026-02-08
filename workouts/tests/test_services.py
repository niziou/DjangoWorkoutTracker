from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from workouts.models import ExerciseAlias, MuscleGroup
from workouts.services import (
    calculate_tonnage,
    count_sets_by_muscle_group,
    get_best_set_for_exercise,
    parse_entries,
)
from workouts.utils import normalize_text
from workouts.tests.factories import (
    add_performed_exercise,
    create_exercise,
    create_user,
    create_workout_session,
    make_set,
)


class ServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = create_user()
        self.now = timezone.now()

    def test_calculate_tonnage(self) -> None:
        exercise = create_exercise("Bench Press", muscle_group=MuscleGroup.CHEST)
        session = create_workout_session(self.user, performed_at=self.now)
        add_performed_exercise(
            session,
            exercise,
            order_index=1,
            sets=[
                make_set(1, weight_kg=50, reps=5),
                make_set(2, weight_kg=60, reps=3),
                make_set(3, duration_seconds=30),
            ],
        )

        total = calculate_tonnage(self.user, self.now.date(), self.now.date())
        self.assertEqual(total, Decimal("430"))

    def test_get_best_set_for_exercise(self) -> None:
        exercise = create_exercise("Deadlift", muscle_group=MuscleGroup.BACK)
        session = create_workout_session(self.user, performed_at=self.now)
        add_performed_exercise(
            session,
            exercise,
            order_index=1,
            sets=[make_set(1, weight_kg=120, reps=3), make_set(2, weight_kg=120, reps=5)],
        )
        later_session = create_workout_session(self.user, performed_at=self.now + timedelta(days=1))
        add_performed_exercise(
            later_session,
            exercise,
            order_index=1,
            sets=[make_set(1, weight_kg=125, reps=2)],
        )

        best = get_best_set_for_exercise(self.user, exercise.id)
        assert best is not None
        self.assertEqual(best["performed_set"].weight_kg, Decimal("125"))
        self.assertEqual(best["performed_set"].reps, 2)

    def test_count_sets_by_muscle_group(self) -> None:
        legs = create_exercise("Back Squat", muscle_group=MuscleGroup.LEGS)
        chest = create_exercise("Bench Press", muscle_group=MuscleGroup.CHEST)
        session = create_workout_session(self.user, performed_at=self.now)
        add_performed_exercise(
            session,
            legs,
            order_index=1,
            sets=[make_set(1, weight_kg=80, reps=5), make_set(2, weight_kg=90, reps=5)],
        )
        add_performed_exercise(
            session,
            chest,
            order_index=2,
            sets=[make_set(1, weight_kg=60, reps=8)],
        )

        counts = count_sets_by_muscle_group(self.user, self.now.date(), self.now.date())
        self.assertEqual(counts[MuscleGroup.LEGS], 2)
        self.assertEqual(counts[MuscleGroup.CHEST], 1)

    def test_parse_entries_weight_and_time(self) -> None:
        bench = create_exercise("Bench Press", muscle_group=MuscleGroup.CHEST)
        hollow = create_exercise("Hollow Hold", muscle_group=MuscleGroup.CORE, is_bodyweight=True)

        ExerciseAlias.objects.create(
            exercise=bench,
            alias="bench press",
            normalized_alias=normalize_text("bench press"),
        )
        ExerciseAlias.objects.create(
            exercise=hollow,
            alias="hollow hold",
            normalized_alias=normalize_text("hollow hold"),
        )

        exercises_payload, errors = parse_entries(
            ["3x5 bench press 75kg", "3x30s hollow hold"]
        )
        self.assertFalse(errors)
        self.assertEqual(len(exercises_payload), 2)
        self.assertEqual(exercises_payload[0]["sets"][0]["reps"], 5)
        self.assertEqual(exercises_payload[1]["sets"][0]["duration_seconds"], 30)

    def test_parse_entries_creates_unknown_exercise(self) -> None:
        exercises_payload, errors = parse_entries(["3x10 Seated Cable Row 50kg"])
        self.assertFalse(errors)
        self.assertEqual(len(exercises_payload), 1)
        self.assertEqual(exercises_payload[0]["exercise"].slug, "seated-cable-row")
