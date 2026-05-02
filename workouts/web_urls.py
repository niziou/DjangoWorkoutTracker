from __future__ import annotations

from django.urls import path

from .web_views import (
    WorkoutCalendarView,
    ExerciseVolumeView,
    WorkoutCreateView,
    WorkoutDetailView,
    WorkoutDraftView,
    WorkoutPhotoImportView,
    WorkoutListView,
    WorkoutStatsView,
)

urlpatterns = [
    path("", WorkoutListView.as_view(), name="workout-list"),
    path("workouts/new/", WorkoutCreateView.as_view(), name="workout-create"),
    path("workouts/<int:pk>/", WorkoutDetailView.as_view(), name="workout-detail"),
    path("workouts/draft/", WorkoutDraftView.as_view(), name="workout-draft"),
    path(
        "workouts/import-photo/",
        WorkoutPhotoImportView.as_view(),
        name="workout-import-photo",
    ),
    path("calendar/", WorkoutCalendarView.as_view(), name="workout-calendar"),
    path("stats/", WorkoutStatsView.as_view(), name="workout-stats"),
    path("stats/exercise/", ExerciseVolumeView.as_view(), name="exercise-volume"),
]
