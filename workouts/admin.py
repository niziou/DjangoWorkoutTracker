from __future__ import annotations

from django.contrib import admin

from .models import Exercise, ExerciseAlias, PerformedExercise, PerformedSet, WorkoutDraft, WorkoutSession


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "primary_muscle_group", "is_bodyweight", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("primary_muscle_group", "is_bodyweight")


@admin.register(ExerciseAlias)
class ExerciseAliasAdmin(admin.ModelAdmin):
    list_display = ("alias", "exercise", "normalized_alias", "created_at")
    search_fields = ("alias", "normalized_alias", "exercise__name")


class PerformedSetInline(admin.TabularInline):
    model = PerformedSet
    extra = 0


class PerformedExerciseInline(admin.TabularInline):
    model = PerformedExercise
    extra = 0


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ("performed_at", "user", "template_name", "created_at")
    search_fields = ("template_name", "notes")
    list_filter = ("performed_at",)
    inlines = [PerformedExerciseInline]


@admin.register(PerformedExercise)
class PerformedExerciseAdmin(admin.ModelAdmin):
    list_display = ("workout_session", "exercise", "order_index")
    search_fields = ("exercise__name", "workout_session__template_name")
    list_filter = ("exercise__primary_muscle_group",)
    inlines = [PerformedSetInline]


@admin.register(PerformedSet)
class PerformedSetAdmin(admin.ModelAdmin):
    list_display = ("performed_exercise", "set_index", "weight_kg", "reps", "duration_seconds", "is_warmup")
    search_fields = ("performed_exercise__exercise__name",)
    list_filter = ("is_warmup",)


@admin.register(WorkoutDraft)
class WorkoutDraftAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
    search_fields = ("user__username",)
