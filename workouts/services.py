from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, DecimalField, F, ExpressionWrapper, Sum
from django.utils import timezone

from .models import Exercise, MuscleGroup, PerformedExercise, PerformedSet, WorkoutSession

User = get_user_model()


def get_default_user(user: Optional[User]) -> User:
    """Return provided user or a singleton default user."""
    if user and user.is_authenticated:
        return user
    existing_user = User.objects.first()
    if existing_user:
        return existing_user
    return User.objects.create_user(username="default")


def _normalize_start(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.combine(value, time.min)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def _normalize_end(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.combine(value, time.max)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def create_workout_from_payload(user: User, data: dict[str, Any]) -> WorkoutSession:
    """Create a workout session with nested exercises and sets."""
    exercises_data = data.pop("exercises", [])
    with transaction.atomic():
        session = WorkoutSession.objects.create(user=user, **data)
        for exercise_data in exercises_data:
            sets_data = exercise_data.pop("sets", [])
            performed_exercise = PerformedExercise.objects.create(
                workout_session=session, **exercise_data
            )
            for set_data in sets_data:
                PerformedSet.objects.create(
                    performed_exercise=performed_exercise, **set_data
                )
    return session


def calculate_tonnage(user: User, date_from: date | datetime, date_to: date | datetime) -> Decimal:
    start = _normalize_start(date_from)
    end = _normalize_end(date_to)

    weighted_sets = PerformedSet.objects.filter(
        performed_exercise__workout_session__user=user,
        performed_exercise__workout_session__performed_at__gte=start,
        performed_exercise__workout_session__performed_at__lte=end,
        weight_kg__isnull=False,
        reps__isnull=False,
    )

    tonnage_expr = ExpressionWrapper(
        F("weight_kg") * F("reps"), output_field=DecimalField(max_digits=10, decimal_places=2)
    )
    total = weighted_sets.aggregate(total=Sum(tonnage_expr))["total"]
    return total or Decimal("0")


def estimate_one_rep_max(weight_kg: Decimal, reps: int) -> Decimal:
    one_rm = weight_kg * (Decimal("1") + (Decimal(reps) / Decimal("30")))
    return one_rm.quantize(Decimal("0.1"))


def get_best_set_for_exercise(
    user: User,
    exercise_id: int,
    date_from: Optional[date | datetime] = None,
    date_to: Optional[date | datetime] = None,
) -> Optional[dict[str, Any]]:
    filters: dict[str, Any] = {
        "performed_exercise__exercise__id": exercise_id,
        "performed_exercise__workout_session__user": user,
        "weight_kg__isnull": False,
        "reps__isnull": False,
    }

    if date_from:
        filters["performed_exercise__workout_session__performed_at__gte"] = _normalize_start(
            date_from
        )
    if date_to:
        filters["performed_exercise__workout_session__performed_at__lte"] = _normalize_end(
            date_to
        )

    best_set = (
        PerformedSet.objects.filter(**filters)
        .select_related("performed_exercise__exercise", "performed_exercise__workout_session")
        .order_by("-weight_kg", "-reps", "-performed_exercise__workout_session__performed_at")
        .first()
    )
    if not best_set:
        return None

    exercise: Exercise = best_set.performed_exercise.exercise
    session: WorkoutSession = best_set.performed_exercise.workout_session
    estimated_1rm = estimate_one_rep_max(Decimal(best_set.weight_kg), int(best_set.reps))

    return {
        "exercise": exercise,
        "workout_session": session,
        "performed_set": best_set,
        "estimated_1rm": estimated_1rm,
    }


def count_sets_by_muscle_group(
    user: User, date_from: date | datetime, date_to: date | datetime
) -> dict[str, int]:
    start = _normalize_start(date_from)
    end = _normalize_end(date_to)

    qs = PerformedSet.objects.filter(
        performed_exercise__workout_session__user=user,
        performed_exercise__workout_session__performed_at__gte=start,
        performed_exercise__workout_session__performed_at__lte=end,
    )

    aggregates = (
        qs.values("performed_exercise__exercise__primary_muscle_group")
        .annotate(total=Count("id"))
        .order_by()
    )

    results: dict[str, int] = {choice: 0 for choice, _ in MuscleGroup.choices}
    for row in aggregates:
        group = row["performed_exercise__exercise__primary_muscle_group"]
        results[group] = row["total"]
    return results
