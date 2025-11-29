from __future__ import annotations

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Exercise",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(unique=True)),
                (
                    "primary_muscle_group",
                    models.CharField(
                        choices=[
                            ("CHEST", "Chest"),
                            ("BACK", "Back"),
                            ("LEGS", "Legs"),
                            ("SHOULDERS", "Shoulders"),
                            ("BICEPS", "Biceps"),
                            ("TRICEPS", "Triceps"),
                            ("CORE", "Core"),
                            ("CALVES", "Calves"),
                            ("OTHER", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                ("is_bodyweight", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="WorkoutSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("performed_at", models.DateTimeField()),
                ("template_name", models.CharField(blank=True, max_length=100)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workouts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-performed_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="PerformedExercise",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_index", models.PositiveIntegerField()),
                ("notes", models.TextField(blank=True)),
                (
                    "exercise",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="workouts.exercise"),
                ),
                (
                    "workout_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exercises",
                        to="workouts.workoutsession",
                    ),
                ),
            ],
            options={
                "ordering": ["order_index"],
            },
        ),
        migrations.CreateModel(
            name="PerformedSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("set_index", models.PositiveIntegerField()),
                ("weight_kg", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("reps", models.PositiveIntegerField(blank=True, null=True)),
                ("duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("is_warmup", models.BooleanField(default=False)),
                (
                    "performed_exercise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sets",
                        to="workouts.performedexercise",
                    ),
                ),
            ],
            options={
                "ordering": ["set_index"],
            },
        ),
        migrations.AddConstraint(
            model_name="performedset",
            constraint=models.UniqueConstraint(
                fields=("performed_exercise", "set_index"), name="unique_set_order_per_exercise"
            ),
        ),
        migrations.AddConstraint(
            model_name="performedexercise",
            constraint=models.UniqueConstraint(
                fields=("workout_session", "order_index"), name="unique_exercise_order_per_workout"
            ),
        ),
    ]
