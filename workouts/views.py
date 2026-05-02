from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WorkoutSession
from .serializers import WorkoutSessionSerializer
from .services import calculate_tonnage, count_sets_by_muscle_group, get_best_set_for_exercise


def _parse_iso_value(raw_value: Optional[str]) -> Optional[date | datetime]:
    if not raw_value:
        return None
    raw_value = raw_value.strip()
    if "T" not in raw_value and " " not in raw_value:
        return parse_date(raw_value)
    dt = parse_datetime(raw_value)
    if dt:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    return parse_date(raw_value)


def _normalize_for_filter(value: Optional[date | datetime], *, is_end: bool = False) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.combine(value, time.max if is_end else time.min)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


class WorkoutSessionViewSet(viewsets.ModelViewSet):
    serializer_class = WorkoutSessionSerializer
    http_method_names = ["get", "post", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = (
            WorkoutSession.objects.filter(user=user)
            .prefetch_related("exercises__sets", "exercises__exercise")
            .order_by("-performed_at", "-id")
        )

        raw_from = self.request.query_params.get("from")
        raw_to = self.request.query_params.get("to")
        parsed_from = _normalize_for_filter(_parse_iso_value(raw_from)) if raw_from else None
        parsed_to = _normalize_for_filter(_parse_iso_value(raw_to), is_end=True) if raw_to else None

        if parsed_from:
            queryset = queryset.filter(performed_at__gte=parsed_from)
        if parsed_to:
            queryset = queryset.filter(performed_at__lte=parsed_to)
        return queryset

    def perform_create(self, serializer: WorkoutSessionSerializer) -> None:
        serializer.save()


class TonnageStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        raw_from = request.query_params.get("from")
        raw_to = request.query_params.get("to")
        date_from = _parse_iso_value(raw_from)
        date_to = _parse_iso_value(raw_to)

        if not date_from or not date_to:
            return Response(
                {"detail": "Query params 'from' and 'to' are required (ISO date)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        total = calculate_tonnage(user, date_from, date_to)
        return Response(
            {
                "from": raw_from,
                "to": raw_to,
                "total_tonnage": float(total),
            }
        )


class BestExerciseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        exercise_id = request.query_params.get("exercise_id")
        if not exercise_id:
            return Response(
                {"detail": "Query param 'exercise_id' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            exercise_id_int = int(exercise_id)
        except ValueError:
            return Response(
                {"detail": "Invalid 'exercise_id'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_from = request.query_params.get("from")
        raw_to = request.query_params.get("to")
        date_from = _parse_iso_value(raw_from)
        date_to = _parse_iso_value(raw_to)

        user = request.user
        best = get_best_set_for_exercise(user, exercise_id_int, date_from, date_to)
        if not best:
            return Response({"detail": "No matching sets found."}, status=status.HTTP_404_NOT_FOUND)

        performed_set = best["performed_set"]
        session = best["workout_session"]
        exercise = best["exercise"]

        return Response(
            {
                "exercise_id": exercise.id,
                "exercise_name": exercise.name,
                "performed_at": session.performed_at,
                "weight_kg": float(performed_set.weight_kg),
                "reps": performed_set.reps,
                "estimated_1rm": float(best["estimated_1rm"]),
            }
        )


class SetsByMuscleGroupView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        raw_from = request.query_params.get("from")
        raw_to = request.query_params.get("to")
        date_from = _parse_iso_value(raw_from)
        date_to = _parse_iso_value(raw_to)

        if not date_from or not date_to:
            return Response(
                {"detail": "Query params 'from' and 'to' are required (ISO date)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        counts = count_sets_by_muscle_group(user, date_from, date_to)
        return Response({"from": raw_from, "to": raw_to, "groups": counts})


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})
