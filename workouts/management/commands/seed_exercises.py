from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from workouts.models import Exercise, MuscleGroup

DEFAULT_EXERCISES = [
    ("Back Squat", MuscleGroup.LEGS, False),
    ("Bench Press", MuscleGroup.CHEST, False),
    ("Barbell Row", MuscleGroup.BACK, False),
    ("Pull-Up", MuscleGroup.BACK, True),
    ("Lateral Raise", MuscleGroup.SHOULDERS, False),
    ("Biceps Curl", MuscleGroup.BICEPS, False),
    ("Triceps Extension", MuscleGroup.TRICEPS, False),
    ("Hip Thrust", MuscleGroup.LEGS, False),
    ("Hollow Hold", MuscleGroup.CORE, True),
    ("Calf Raise", MuscleGroup.CALVES, False),
]


class Command(BaseCommand):
    help = "Seed a small library of default exercises."

    def handle(self, *args, **options):
        created_count = 0
        for name, muscle_group, is_bodyweight in DEFAULT_EXERCISES:
            slug = slugify(name)
            _, created = Exercise.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "primary_muscle_group": muscle_group,
                    "is_bodyweight": is_bodyweight,
                },
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Seed complete. Created {created_count} new exercises.")
        )
