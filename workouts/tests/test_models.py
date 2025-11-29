from __future__ import annotations

from django.test import TestCase

from workouts.tests.factories import (
    add_performed_exercise,
    create_exercise,
    create_user,
    create_workout_session,
    make_set,
)


class WorkoutModelTests(TestCase):
    def test_create_workout_with_nested_items(self) -> None:
        user = create_user()
        exercise = create_exercise()
        session = create_workout_session(user, template_name="Training A")
        add_performed_exercise(
            session,
            exercise,
            order_index=1,
            sets=[make_set(1, weight_kg=50, reps=5), make_set(2, weight_kg=60, reps=5)],
        )

        self.assertEqual(session.exercises.count(), 1)
        performed_exercise = session.exercises.first()
        assert performed_exercise is not None
        self.assertEqual(performed_exercise.sets.count(), 2)
