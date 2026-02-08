from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.text import slugify

from .utils import normalize_text

User = get_user_model()


class MuscleGroup(models.TextChoices):
    CHEST = "CHEST", "Chest"
    BACK = "BACK", "Back"
    LEGS = "LEGS", "Legs"
    SHOULDERS = "SHOULDERS", "Shoulders"
    BICEPS = "BICEPS", "Biceps"
    TRICEPS = "TRICEPS", "Triceps"
    CORE = "CORE", "Core"
    CALVES = "CALVES", "Calves"
    OTHER = "OTHER", "Other"


class Exercise(models.Model):
    name: str = models.CharField(max_length=100, unique=True)
    slug: str = models.SlugField(unique=True)
    primary_muscle_group: str = models.CharField(
        max_length=20, choices=MuscleGroup.choices
    )
    is_bodyweight: bool = models.BooleanField(default=False)
    created_at: Any = models.DateTimeField(auto_now_add=True)
    updated_at: Any = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class ExerciseAlias(models.Model):
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="aliases")
    alias: str = models.CharField(max_length=100)
    normalized_alias: str = models.CharField(max_length=100, unique=True, db_index=True)
    created_at: Any = models.DateTimeField(auto_now_add=True)
    updated_at: Any = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["alias"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.normalized_alias = normalize_text(self.alias)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.alias} -> {self.exercise.name}"


class WorkoutSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workouts")
    performed_at: Any = models.DateTimeField()
    template_name: str = models.CharField(max_length=100, blank=True)
    notes: str = models.TextField(blank=True)
    created_at: Any = models.DateTimeField(auto_now_add=True)
    updated_at: Any = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-performed_at", "-id"]

    def __str__(self) -> str:
        return f"Workout on {self.performed_at.isoformat()}"


class PerformedExercise(models.Model):
    workout_session = models.ForeignKey(
        WorkoutSession, on_delete=models.CASCADE, related_name="exercises"
    )
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    order_index: int = models.PositiveIntegerField()
    notes: str = models.TextField(blank=True)

    class Meta:
        ordering = ["order_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["workout_session", "order_index"],
                name="unique_exercise_order_per_workout",
            )
        ]

    def __str__(self) -> str:
        return f"{self.exercise.name} (#{self.order_index})"


class PerformedSet(models.Model):
    performed_exercise = models.ForeignKey(
        PerformedExercise, on_delete=models.CASCADE, related_name="sets"
    )
    set_index: int = models.PositiveIntegerField()
    weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    reps = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    is_warmup: bool = models.BooleanField(default=False)

    class Meta:
        ordering = ["set_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["performed_exercise", "set_index"],
                name="unique_set_order_per_exercise",
            )
        ]

    def __str__(self) -> str:
        return f"Set #{self.set_index} for {self.performed_exercise}"


class WorkoutDraft(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="workout_draft")
    payload: Any = models.JSONField(default=dict)
    updated_at: Any = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Draft for {self.user}"
