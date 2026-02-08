from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from .models import WorkoutDraft, WorkoutSession
from .services import create_workout_from_payload, parse_entries


class WorkoutListView(LoginRequiredMixin, ListView):
    model = WorkoutSession
    template_name = "workouts/workout_list.html"
    context_object_name = "workouts"
    paginate_by = 20

    def get_queryset(self):
        return (
            WorkoutSession.objects.filter(user=self.request.user)
            .prefetch_related("exercises__sets", "exercises__exercise")
            .order_by("-performed_at", "-id")
        )


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
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        performed_at_raw = request.POST.get("performed_at", "").strip()
        template_name = request.POST.get("template_name", "").strip()
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
                "notes": notes,
                "entries": entries,
            }
            return render(
                request,
                self.template_name,
                {
                    "draft_payload": draft_payload,
                    "errors": errors,
                },
            )

        payload = {
            "performed_at": performed_at,
            "template_name": template_name,
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
