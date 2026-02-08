from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from workouts.views import (
    BestExerciseView,
    HealthView,
    SetsByMuscleGroupView,
    TonnageStatsView,
    WorkoutSessionViewSet,
)

router = DefaultRouter()
router.register("workouts", WorkoutSessionViewSet, basename="workout-session")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("workouts.web_urls")),
    path(
        "api/",
        include(
            [
                path("", include(router.urls)),
                path("stats/tonnage/", TonnageStatsView.as_view(), name="stats-tonnage"),
                path(
                    "stats/best-exercise/",
                    BestExerciseView.as_view(),
                    name="stats-best-exercise",
                ),
                path(
                    "stats/sets-by-muscle-group/",
                    SetsByMuscleGroupView.as_view(),
                    name="stats-sets-by-muscle-group",
                ),
                path("health/", HealthView.as_view(), name="health"),
            ]
        ),
    ),
]
