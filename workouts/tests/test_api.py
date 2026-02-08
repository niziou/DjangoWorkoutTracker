from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from workouts.models import MuscleGroup, WorkoutSession
from workouts.tests.factories import (
    add_performed_exercise,
    create_exercise,
    create_user,
    create_workout_session,
    make_set,
)


class WorkoutAPITests(APITestCase):
    def setUp(self) -> None:
        self.user = create_user()
        self.exercise = create_exercise("Back Squat", muscle_group=MuscleGroup.LEGS)
        self.client.force_authenticate(user=self.user)

    def test_post_workout_creates_nested_objects(self) -> None:
        performed_at = timezone.now().isoformat()
        payload = {
            "performed_at": performed_at,
            "template_name": "Training A – Week 4",
            "notes": "Felt strong.",
            "exercises": [
                {
                    "exercise": self.exercise.id,
                    "order_index": 1,
                    "notes": "",
                    "sets": [
                        {"set_index": 1, "weight_kg": 20, "reps": 5, "is_warmup": True},
                        {"set_index": 2, "weight_kg": 40, "reps": 5, "is_warmup": True},
                        {"set_index": 3, "weight_kg": 60, "reps": 5, "is_warmup": False},
                    ],
                }
            ],
        }

        response = self.client.post("/api/workouts/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertEqual(WorkoutSession.objects.count(), 1)
        session = WorkoutSession.objects.first()
        assert session is not None
        self.assertEqual(session.exercises.count(), 1)
        self.assertEqual(session.exercises.first().sets.count(), 3)

    def test_tonnage_endpoint(self) -> None:
        session = create_workout_session(self.user, performed_at=timezone.now())
        add_performed_exercise(
            session,
            self.exercise,
            order_index=1,
            sets=[make_set(1, weight_kg=50, reps=5), make_set(2, weight_kg=60, reps=3)],
        )

        date_str = session.performed_at.date().isoformat()
        response = self.client.get("/api/stats/tonnage/", {"from": date_str, "to": date_str})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_tonnage"], float(Decimal("430")))

    def test_sets_by_muscle_group_endpoint(self) -> None:
        chest_exercise = create_exercise("Bench Press", muscle_group=MuscleGroup.CHEST)
        session = create_workout_session(self.user, performed_at=timezone.now())
        add_performed_exercise(
            session,
            self.exercise,
            order_index=1,
            sets=[make_set(1, weight_kg=80, reps=5), make_set(2, weight_kg=90, reps=5)],
        )
        add_performed_exercise(
            session,
            chest_exercise,
            order_index=2,
            sets=[make_set(1, weight_kg=60, reps=8)],
        )

        date_str = session.performed_at.date().isoformat()
        response = self.client.get(
            "/api/stats/sets-by-muscle-group/", {"from": date_str, "to": date_str}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["groups"][MuscleGroup.LEGS], 2)
        self.assertEqual(response.data["groups"][MuscleGroup.CHEST], 1)
