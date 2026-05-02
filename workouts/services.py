from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import re
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, DecimalField, F, ExpressionWrapper, Sum
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone
from django.utils.text import slugify

from .models import Exercise, ExerciseAlias, MuscleGroup, PerformedExercise, PerformedSet, WorkoutSession
from .utils import normalize_text

User = get_user_model()

class QuickEntryParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedSet:
    weight_kg: Decimal | None
    reps: int | None
    duration_seconds: int | None
    is_warmup: bool = False


@dataclass(frozen=True)
class ParsedExerciseEntry:
    exercise: Exercise
    sets: list[ParsedSet]


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


_WEIGHT_RE = re.compile(
    r"^\s*(?P<sets>\d+)\s*x\s*(?P<reps>\d+)\s+(?P<exercise>.+?)\s+(?P<weight>\d+(?:[.,]\d+)?)\s*(kg)?\s*$",
    re.IGNORECASE,
)
_TIME_RE = re.compile(
    r"^\s*(?P<sets>\d+)\s*x\s*(?P<duration>\d+)\s*(s|sec|secs|second|seconds)\s+(?P<exercise>.+?)\s*$",
    re.IGNORECASE,
)
_BODYWEIGHT_RE = re.compile(
    r"^\s*(?P<sets>\d+)\s*x\s*(?P<reps>\d+)\s+(?P<exercise>.+?)\s*$",
    re.IGNORECASE,
)
_DETAILED_ENTRY_RE = re.compile(
    r"^\s*(?P<exercise>[^:]+?)\s*:\s*(?P<sets>.+?)\s*$",
    re.IGNORECASE,
)
_DETAILED_WEIGHT_SET_RE = re.compile(
    r"^\s*(?P<weight>\d+(?:[.,]\d+)?)\s*(kg)?\s*x\s*(?P<reps>\d+)\s*$",
    re.IGNORECASE,
)
_DETAILED_DURATION_SET_RE = re.compile(
    r"^\s*(?P<duration>\d+)\s*(s|sec|secs|second|seconds)\s*$",
    re.IGNORECASE,
)
_DETAILED_BODYWEIGHT_SET_RE = re.compile(
    r"^\s*(?:x\s*)?(?P<reps>\d+)\s*(reps?)?\s*$",
    re.IGNORECASE,
)


def resolve_exercise(
    raw_name: str,
    *,
    is_bodyweight_hint: bool | None = None,
    allow_create: bool = True,
) -> Exercise:
    normalized = normalize_text(raw_name)
    alias = (
        ExerciseAlias.objects.select_related("exercise")
        .filter(normalized_alias=normalized)
        .first()
    )
    if alias:
        return alias.exercise

    slug = slugify(raw_name)
    exercise = Exercise.objects.filter(slug=slug).first()
    if exercise:
        return exercise

    exercise = Exercise.objects.filter(name__iexact=raw_name.strip()).first()
    if exercise:
        return exercise

    name = raw_name.strip()
    if not name:
        raise QuickEntryParseError("Exercise name is missing.")

    if not allow_create:
        raise QuickEntryParseError(f"Unknown exercise '{name}'.")

    is_bodyweight = bool(is_bodyweight_hint) if is_bodyweight_hint is not None else False
    exercise = Exercise.objects.create(
        name=name,
        slug=slugify(name),
        primary_muscle_group=MuscleGroup.OTHER,
        is_bodyweight=is_bodyweight,
    )
    ExerciseAlias.objects.create(
        exercise=exercise,
        alias=name,
        normalized_alias=normalized,
    )
    return exercise


def _build_sets(count: int, *, weight: Decimal | None, reps: int | None, duration: int | None) -> list[ParsedSet]:
    return [
        ParsedSet(weight_kg=weight, reps=reps, duration_seconds=duration, is_warmup=False)
        for _ in range(count)
    ]


def _parse_detailed_entry(
    raw_entry: str, *, allow_create_missing: bool
) -> ParsedExerciseEntry | None:
    match_detailed = _DETAILED_ENTRY_RE.match(raw_entry)
    if not match_detailed:
        return None

    exercise_name = match_detailed.group("exercise").strip()
    raw_sets = match_detailed.group("sets")
    set_tokens = [
        token.strip()
        for token in re.split(r"\s*[,;]\s*", raw_sets)
        if token and token.strip()
    ]
    if not set_tokens:
        raise QuickEntryParseError(f"Exercise '{exercise_name}' has no sets.")

    detailed_kind = ""
    if all(_DETAILED_WEIGHT_SET_RE.match(token) for token in set_tokens):
        detailed_kind = "weight"
    elif all(_DETAILED_DURATION_SET_RE.match(token) for token in set_tokens):
        detailed_kind = "duration"
    elif all(_DETAILED_BODYWEIGHT_SET_RE.match(token) for token in set_tokens):
        detailed_kind = "bodyweight"
    else:
        raise QuickEntryParseError(
            f"Mixed or unsupported set formats for '{exercise_name}'."
        )

    exercise = resolve_exercise(
        exercise_name,
        is_bodyweight_hint=detailed_kind != "weight",
        allow_create=allow_create_missing,
    )
    parsed_sets: list[ParsedSet] = []

    if detailed_kind == "weight":
        for token in set_tokens:
            match_weight = _DETAILED_WEIGHT_SET_RE.match(token)
            assert match_weight is not None
            parsed_sets.append(
                ParsedSet(
                    weight_kg=Decimal(match_weight.group("weight").replace(",", ".")),
                    reps=int(match_weight.group("reps")),
                    duration_seconds=None,
                    is_warmup=False,
                )
            )
        return ParsedExerciseEntry(exercise=exercise, sets=parsed_sets)

    if detailed_kind == "duration":
        for token in set_tokens:
            match_duration = _DETAILED_DURATION_SET_RE.match(token)
            assert match_duration is not None
            parsed_sets.append(
                ParsedSet(
                    weight_kg=None,
                    reps=None,
                    duration_seconds=int(match_duration.group("duration")),
                    is_warmup=False,
                )
            )
        return ParsedExerciseEntry(exercise=exercise, sets=parsed_sets)

    if not exercise.is_bodyweight:
        raise QuickEntryParseError(
            f"Missing weight for '{exercise.name}'. Use format like '3x5 {exercise.name} 75kg'."
        )

    for token in set_tokens:
        match_bodyweight = _DETAILED_BODYWEIGHT_SET_RE.match(token)
        assert match_bodyweight is not None
        parsed_sets.append(
            ParsedSet(
                weight_kg=Decimal("0"),
                reps=int(match_bodyweight.group("reps")),
                duration_seconds=None,
                is_warmup=False,
            )
        )
    return ParsedExerciseEntry(exercise=exercise, sets=parsed_sets)


def parse_quick_entry(
    raw_entry: str, *, allow_create_missing: bool = True
) -> ParsedExerciseEntry:
    raw_entry = raw_entry.strip()
    if not raw_entry:
        raise QuickEntryParseError("Empty entry.")

    detailed_entry = _parse_detailed_entry(
        raw_entry, allow_create_missing=allow_create_missing
    )
    if detailed_entry:
        return detailed_entry

    match_time = _TIME_RE.match(raw_entry)
    if match_time:
        sets = int(match_time.group("sets"))
        duration = int(match_time.group("duration"))
        exercise_name = match_time.group("exercise")
        exercise = resolve_exercise(
            exercise_name,
            is_bodyweight_hint=True,
            allow_create=allow_create_missing,
        )
        return ParsedExerciseEntry(exercise=exercise, sets=_build_sets(sets, weight=None, reps=None, duration=duration))

    match_weight = _WEIGHT_RE.match(raw_entry)
    if match_weight:
        sets = int(match_weight.group("sets"))
        reps = int(match_weight.group("reps"))
        weight_raw = match_weight.group("weight").replace(",", ".")
        weight = Decimal(weight_raw)
        exercise_name = match_weight.group("exercise")
        exercise = resolve_exercise(
            exercise_name,
            is_bodyweight_hint=False,
            allow_create=allow_create_missing,
        )
        return ParsedExerciseEntry(exercise=exercise, sets=_build_sets(sets, weight=weight, reps=reps, duration=None))

    match_bodyweight = _BODYWEIGHT_RE.match(raw_entry)
    if match_bodyweight:
        sets = int(match_bodyweight.group("sets"))
        reps = int(match_bodyweight.group("reps"))
        exercise_name = match_bodyweight.group("exercise")
        exercise = resolve_exercise(
            exercise_name,
            is_bodyweight_hint=True,
            allow_create=allow_create_missing,
        )
        if not exercise.is_bodyweight:
            raise QuickEntryParseError(
                f"Missing weight for '{exercise.name}'. Use format like '3x5 {exercise.name} 75kg'."
            )
        return ParsedExerciseEntry(
            exercise=exercise,
            sets=_build_sets(sets, weight=Decimal("0"), reps=reps, duration=None),
        )

    raise QuickEntryParseError(
        "Unsupported format. Use '3x5 bench press 75kg', '3x30s hollow hold', or 'bench press: 20kg x 5, 40kg x 5'."
    )


def parse_entries(
    entries: list[str], *, allow_create_missing: bool = True
) -> tuple[list[dict[str, Any]], list[str]]:
    exercises_payload: list[dict[str, Any]] = []
    errors: list[str] = []
    order_index = 1
    for raw_entry in entries:
        if not raw_entry or not raw_entry.strip():
            continue
        try:
            parsed = parse_quick_entry(
                raw_entry, allow_create_missing=allow_create_missing
            )
        except QuickEntryParseError as exc:
            errors.append(f"{raw_entry}: {exc}")
            continue

        sets_payload = [
            {
                "set_index": idx + 1,
                "weight_kg": parsed_set.weight_kg,
                "reps": parsed_set.reps,
                "duration_seconds": parsed_set.duration_seconds,
                "is_warmup": parsed_set.is_warmup,
            }
            for idx, parsed_set in enumerate(parsed.sets)
        ]
        exercises_payload.append(
            {
                "exercise": parsed.exercise,
                "order_index": order_index,
                "notes": "",
                "sets": sets_payload,
            }
        )
        order_index += 1
    return exercises_payload, errors


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


def get_weekly_tonnage(
    user: User, *, weeks: int = 12, end_date: date | None = None
) -> list[dict[str, Any]]:
    if weeks <= 0:
        return []

    end_date = end_date or timezone.localdate()
    start_date = end_date - timedelta(weeks=weeks - 1)
    start_of_week = start_date - timedelta(days=start_date.weekday())
    end_of_week = end_date - timedelta(days=end_date.weekday())

    start = _normalize_start(start_of_week)
    end = _normalize_end(end_date)

    weighted_sets = PerformedSet.objects.filter(
        performed_exercise__workout_session__user=user,
        performed_exercise__workout_session__performed_at__gte=start,
        performed_exercise__workout_session__performed_at__lte=end,
        weight_kg__isnull=False,
        reps__isnull=False,
    )

    tonnage_expr = ExpressionWrapper(
        F("weight_kg") * F("reps"), output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    aggregates = (
        weighted_sets.annotate(
            week=TruncWeek(
                "performed_exercise__workout_session__performed_at",
                tzinfo=timezone.get_current_timezone(),
            )
        )
        .values("week")
        .annotate(total=Sum(tonnage_expr))
        .order_by("week")
    )

    totals_by_week: dict[date, float] = {}
    for row in aggregates:
        week_start = row["week"].date() if row["week"] else None
        if week_start:
            totals_by_week[week_start] = float(row["total"] or Decimal("0"))

    results: list[dict[str, Any]] = []
    current = start_of_week
    while current <= end_of_week:
        results.append(
            {
                "week": current.isoformat(),
                "total": totals_by_week.get(current, 0.0),
            }
        )
        current += timedelta(weeks=1)
    return results


def get_exercise_weekly_volume(
    user: User,
    exercise_id: int,
    *,
    weeks: int = 12,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    if weeks <= 0:
        return []

    end_date = end_date or timezone.localdate()
    start_date = end_date - timedelta(weeks=weeks - 1)
    start_of_week = start_date - timedelta(days=start_date.weekday())
    end_of_week = end_date - timedelta(days=end_date.weekday())

    start = _normalize_start(start_of_week)
    end = _normalize_end(end_date)

    weighted_sets = PerformedSet.objects.filter(
        performed_exercise__workout_session__user=user,
        performed_exercise__exercise__id=exercise_id,
        performed_exercise__workout_session__performed_at__gte=start,
        performed_exercise__workout_session__performed_at__lte=end,
        weight_kg__isnull=False,
        reps__isnull=False,
    )

    tonnage_expr = ExpressionWrapper(
        F("weight_kg") * F("reps"), output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    aggregates = (
        weighted_sets.annotate(
            week=TruncWeek(
                "performed_exercise__workout_session__performed_at",
                tzinfo=timezone.get_current_timezone(),
            )
        )
        .values("week")
        .annotate(total=Sum(tonnage_expr))
        .order_by("week")
    )

    totals_by_week: dict[date, float] = {}
    for row in aggregates:
        week_start = row["week"].date() if row["week"] else None
        if week_start:
            totals_by_week[week_start] = float(row["total"] or Decimal("0"))

    results: list[dict[str, Any]] = []
    current = start_of_week
    while current <= end_of_week:
        results.append(
            {
                "week": current.isoformat(),
                "total": totals_by_week.get(current, 0.0),
            }
        )
        current += timedelta(weeks=1)
    return results


def get_daily_tonnage(
    user: User, date_from: date | datetime, date_to: date | datetime
) -> dict[date, float]:
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
        F("weight_kg") * F("reps"), output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    aggregates = (
        weighted_sets.annotate(
            day=TruncDate(
                "performed_exercise__workout_session__performed_at",
                tzinfo=timezone.get_current_timezone(),
            )
        )
        .values("day")
        .annotate(total=Sum(tonnage_expr))
        .order_by("day")
    )

    results: dict[date, float] = {}
    for row in aggregates:
        raw_day = row["day"]
        if not raw_day:
            continue
        if isinstance(raw_day, datetime):
            day = raw_day.date()
        else:
            day = raw_day
        results[day] = float(row["total"] or Decimal("0"))
    return results
