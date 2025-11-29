from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify

from workouts.models import Exercise, MuscleGroup, PerformedExercise, PerformedSet, WorkoutSession

User = get_user_model()


def create_user(username: str = "tester") -> User:
    return User.objects.create_user(username=username)


def create_exercise(
    name: str = "Back Squat",
    muscle_group: str = MuscleGroup.LEGS,
    is_bodyweight: bool = False,
) -> Exercise:
    return Exercise.objects.create(
        name=name,
        slug=slugify(name),
        primary_muscle_group=muscle_group,
        is_bodyweight=is_bodyweight,
    )


def create_workout_session(
    user: User,
    performed_at: datetime | None = None,
    template_name: str = "Session",
    notes: str = "",
) -> WorkoutSession:
    performed_at = performed_at or timezone.now()
    return WorkoutSession.objects.create(
        user=user,
        performed_at=performed_at,
        template_name=template_name,
        notes=notes,
    )


def add_performed_exercise(
    session: WorkoutSession,
    exercise: Exercise,
    order_index: int = 1,
    notes: str = "",
    sets: Iterable[dict] | None = None,
) -> PerformedExercise:
    performed_exercise = PerformedExercise.objects.create(
        workout_session=session,
        exercise=exercise,
        order_index=order_index,
        notes=notes,
    )
    for set_data in sets or []:
        PerformedSet.objects.create(performed_exercise=performed_exercise, **set_data)
    return performed_exercise


def make_set(
    set_index: int,
    weight_kg: Decimal | float | None = None,
    reps: int | None = None,
    duration_seconds: int | None = None,
    is_warmup: bool = False,
) -> dict:
    return {
        "set_index": set_index,
        "weight_kg": Decimal(str(weight_kg)) if weight_kg is not None else None,
        "reps": reps,
        "duration_seconds": duration_seconds,
        "is_warmup": is_warmup,
    }
