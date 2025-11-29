from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from workouts.models import Exercise, MuscleGroup

DEFAULT_EXERCISES = [
    # Skill block (muscle-up)
    ("Passive Hang (Zwis pasywny)", MuscleGroup.BACK, True),
    ("Active Hang (Zwis aktywny)", MuscleGroup.BACK, True),
    ("Scapular Pull-Up", MuscleGroup.BACK, True),
    ("Band Pull-Apart", MuscleGroup.SHOULDERS, True),
    ("External Rotation", MuscleGroup.SHOULDERS, False),
    ("Australian Pull-Up", MuscleGroup.BACK, True),
    ("Half Explosive Pull-Up", MuscleGroup.BACK, True),
    ("Explosive Pull-Up", MuscleGroup.BACK, True),
    ("High Pull-Up", MuscleGroup.BACK, True),
    ("False Grip Hang", MuscleGroup.BACK, True),
    ("Assisted Muscle-Up (Band)", MuscleGroup.BACK, True),
    # Trening A
    ("Back Squat", MuscleGroup.LEGS, False),
    ("Bench Press", MuscleGroup.CHEST, False),
    ("Barbell Row", MuscleGroup.BACK, False),
    ("Lateral Raise", MuscleGroup.SHOULDERS, False),
    ("Dips", MuscleGroup.CHEST, True),
    ("Biceps Curl", MuscleGroup.BICEPS, False),
    ("Triceps Extension", MuscleGroup.TRICEPS, False),
    ("Hip Thrust", MuscleGroup.LEGS, False),
    ("Hollow Hold", MuscleGroup.CORE, True),
    ("Calf Raise", MuscleGroup.CALVES, False),
    ("Close Grip Bench Press", MuscleGroup.TRICEPS, False),
    # Trening B
    ("Deadlift", MuscleGroup.BACK, False),
    ("Overhead Press", MuscleGroup.SHOULDERS, False),
    ("Chin-Up", MuscleGroup.BACK, True),
    ("Plank", MuscleGroup.CORE, True),
    # Additional
    ("Reverse Fly", MuscleGroup.SHOULDERS, False),
    ("Single-Arm Lateral Raise (45 Bench)", MuscleGroup.SHOULDERS, False),
    ("Single-Arm Landmine Press", MuscleGroup.SHOULDERS, False),
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
