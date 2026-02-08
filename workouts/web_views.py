from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from .models import Exercise, WorkoutDraft, WorkoutSession, WorkoutType
from .services import (
    calculate_tonnage,
    count_sets_by_muscle_group,
    create_workout_from_payload,
    get_daily_tonnage,
    get_exercise_weekly_volume,
    get_weekly_tonnage,
    parse_entries,
)


class WorkoutListView(LoginRequiredMixin, ListView):
    model = WorkoutSession
    template_name = "workouts/workout_list.html"
    context_object_name = "workouts"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            WorkoutSession.objects.filter(user=self.request.user)
            .prefetch_related("exercises__sets", "exercises__exercise")
            .order_by("-performed_at", "-id")
        )
        training_type = self.request.GET.get("training_type", "").strip()
        valid_types = {choice[0] for choice in WorkoutType.choices}
        if training_type in valid_types:
            queryset = queryset.filter(training_type=training_type)
        return queryset

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        context["training_types"] = WorkoutType.choices
        context["selected_training_type"] = self.request.GET.get("training_type", "")
        return context


class WorkoutDetailView(LoginRequiredMixin, DetailView):
    model = WorkoutSession
    template_name = "workouts/workout_detail.html"
    context_object_name = "workout"

    def get_queryset(self):
        return (
            WorkoutSession.objects.filter(user=self.request.user)
            .prefetch_related("exercises__sets", "exercises__exercise")
        )


class WorkoutCreateView(LoginRequiredMixin, View):
    template_name = "workouts/workout_create.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        draft = WorkoutDraft.objects.filter(user=request.user).first()
        initial_payload: dict[str, Any] = draft.payload if draft else {}
        return render(
            request,
            self.template_name,
            {
                "draft_payload": initial_payload,
                "errors": [],
                "training_types": WorkoutType.choices,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        performed_at_raw = request.POST.get("performed_at", "").strip()
        template_name = request.POST.get("template_name", "").strip()
        training_type = request.POST.get("training_type", "").strip()
        notes = request.POST.get("notes", "").strip()
        entries_raw = request.POST.get("entries_json", "[]")

        try:
            entries = json.loads(entries_raw)
            if not isinstance(entries, list):
                raise ValueError("Entries payload must be a list.")
        except ValueError:
            entries = []
            errors = ["Entries payload is invalid JSON."]
        else:
            exercises_payload, errors = parse_entries([str(entry) for entry in entries])
            if not errors and not exercises_payload:
                errors.append("Add at least one entry before saving.")

        performed_at = timezone.now()
        if performed_at_raw:
            try:
                parsed = datetime.fromisoformat(performed_at_raw)
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed)
                performed_at = parsed
            except ValueError:
                errors.append("Invalid performed_at format.")

        if errors:
            draft_payload = {
                "performed_at": performed_at_raw,
                "template_name": template_name,
                "training_type": training_type,
                "notes": notes,
                "entries": entries,
            }
            return render(
                request,
                self.template_name,
                {
                    "draft_payload": draft_payload,
                    "errors": errors,
                    "training_types": WorkoutType.choices,
                },
            )

        payload = {
            "performed_at": performed_at,
            "template_name": template_name,
            "training_type": training_type,
            "notes": notes,
            "exercises": exercises_payload,
        }
        workout = create_workout_from_payload(request.user, payload)
        WorkoutDraft.objects.filter(user=request.user).delete()
        return redirect("workout-detail", pk=workout.pk)


class WorkoutDraftView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> JsonResponse:
        draft = WorkoutDraft.objects.filter(user=request.user).first()
        if not draft:
            return JsonResponse({"entries": []})
        return JsonResponse(draft.payload)

    def post(self, request: HttpRequest) -> JsonResponse:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON."}, status=400)

        WorkoutDraft.objects.update_or_create(
            user=request.user,
            defaults={"payload": payload},
        )
        return JsonResponse({"status": "ok"})


class WorkoutCalendarView(LoginRequiredMixin, View):
    template_name = "workouts/workout_calendar.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        date_param = request.GET.get("date")
        if date_param:
            try:
                selected_date = date.fromisoformat(date_param)
            except ValueError:
                selected_date = timezone.localdate()
        else:
            selected_date = timezone.localdate()

        month_start = selected_date.replace(day=1)
        _, last_day = calendar.monthrange(selected_date.year, selected_date.month)
        month_end = selected_date.replace(day=last_day)

        workouts = WorkoutSession.objects.filter(
            user=request.user,
            performed_at__date__gte=month_start,
            performed_at__date__lte=month_end,
        ).order_by("performed_at")

        workouts_by_day: dict[date, list[WorkoutSession]] = {}
        workout_counts_by_day: dict[date, int] = {}
        for workout in workouts:
            workout_date = workout.performed_at.date()
            workouts_by_day.setdefault(workout_date, []).append(workout)
            workout_counts_by_day[workout_date] = workout_counts_by_day.get(workout_date, 0) + 1

        tonnage_by_day = get_daily_tonnage(request.user, month_start, month_end)

        calendar_weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(
            selected_date.year, selected_date.month
        )

        day_workouts = workouts_by_day.get(selected_date, [])
        selected_day_tonnage = tonnage_by_day.get(selected_date, 0.0)

        prev_month = (month_start - timedelta(days=1)).replace(day=1)
        next_month = (month_end + timedelta(days=1)).replace(day=1)

        calendar_rows: list[list[dict[str, Any]]] = []
        for week in calendar_weeks:
            row: list[dict[str, Any]] = []
            for day in week:
                row.append(
                    {
                        "date": day,
                        "date_key": day.isoformat(),
                        "in_month": day.month == selected_date.month,
                        "count": workout_counts_by_day.get(day, 0),
                        "tonnage": tonnage_by_day.get(day, 0.0),
                    }
                )
            calendar_rows.append(row)

        return render(
            request,
            self.template_name,
            {
                "calendar_rows": calendar_rows,
                "selected_date": selected_date,
                "day_workouts": day_workouts,
                "selected_day_tonnage": selected_day_tonnage,
                "prev_month": prev_month,
                "next_month": next_month,
            },
        )


class WorkoutStatsView(LoginRequiredMixin, View):
    template_name = "workouts/workout_stats.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        today = timezone.localdate()
        month_start = today.replace(day=1)
        _, last_day = calendar.monthrange(today.year, today.month)
        month_end = today.replace(day=last_day)

        sets_by_group = count_sets_by_muscle_group(request.user, month_start, month_end)
        weekly_tonnage = get_weekly_tonnage(request.user, weeks=12, end_date=today)
        total_month_tonnage = calculate_tonnage(request.user, month_start, month_end)

        return render(
            request,
            self.template_name,
            {
                "month_start": month_start,
                "month_end": month_end,
                "sets_by_group": sets_by_group,
                "weekly_tonnage": weekly_tonnage,
                "total_month_tonnage": float(total_month_tonnage),
            },
        )


class ExerciseVolumeView(LoginRequiredMixin, View):
    template_name = "workouts/workout_exercise_volume.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        exercises = list(Exercise.objects.order_by("name"))
        selected_id = request.GET.get("exercise_id")
        selected_exercise = None
        if selected_id and selected_id.isdigit():
            selected_exercise = Exercise.objects.filter(id=int(selected_id)).first()
        if not selected_exercise and exercises:
            selected_exercise = exercises[0]

        volume_data = []
        if selected_exercise:
            volume_data = get_exercise_weekly_volume(
                request.user, selected_exercise.id, weeks=12
            )

        return render(
            request,
            self.template_name,
            {
                "exercises": exercises,
                "selected_exercise": selected_exercise,
                "volume_data": volume_data,
            },
        )
