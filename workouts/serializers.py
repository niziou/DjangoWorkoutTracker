from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Exercise, PerformedExercise, PerformedSet, WorkoutSession
from .services import create_workout_from_payload, get_default_user

User = get_user_model()


class PerformedSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformedSet
        fields = [
            "id",
            "set_index",
            "weight_kg",
            "reps",
            "duration_seconds",
            "is_warmup",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        weight = attrs.get("weight_kg")
        reps = attrs.get("reps")
        duration = attrs.get("duration_seconds")

        has_weight_and_reps = weight is not None and reps is not None
        has_duration = duration is not None

        if not has_weight_and_reps and not has_duration:
            raise serializers.ValidationError(
                "Provide weight and reps or a duration for each set."
            )
        return attrs


class PerformedExerciseSerializer(serializers.ModelSerializer):
    sets = PerformedSetSerializer(many=True)

    class Meta:
        model = PerformedExercise
        fields = ["id", "exercise", "order_index", "notes", "sets"]


class WorkoutSessionSerializer(serializers.ModelSerializer):
    exercises = PerformedExerciseSerializer(many=True)

    class Meta:
        model = WorkoutSession
        fields = ["id", "performed_at", "template_name", "notes", "exercises"]

    def create(self, validated_data: dict[str, Any]) -> WorkoutSession:
        exercises_data = validated_data.pop("exercises", [])
        request = self.context.get("request")
        user: User = get_default_user(request.user if request else None)

        payload = {**validated_data, "exercises": exercises_data}
        return create_workout_from_payload(user, payload)
