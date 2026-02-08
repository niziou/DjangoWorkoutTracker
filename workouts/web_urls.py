from __future__ import annotations

from django.urls import path

from .web_views import WorkoutCreateView, WorkoutDetailView, WorkoutDraftView, WorkoutListView

urlpatterns = [
    path("", WorkoutListView.as_view(), name="workout-list"),
    path("workouts/new/", WorkoutCreateView.as_view(), name="workout-create"),
    path("workouts/<int:pk>/", WorkoutDetailView.as_view(), name="workout-detail"),
    path("workouts/draft/", WorkoutDraftView.as_view(), name="workout-draft"),
]
