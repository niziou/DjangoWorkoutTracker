from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from workouts.models import Exercise, ExerciseAlias, MuscleGroup
from workouts.utils import normalize_text

DEFAULT_EXERCISES = [
    # Skill block (muscle-up)
    {
        "name": "Passive Hang (Zwis pasywny)",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["passive hang", "zwis pasywny"],
    },
    {
        "name": "Active Hang (Zwis aktywny)",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["active hang", "zwis aktywny"],
    },
    {
        "name": "Scapular Pull-Up",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["scapular pull-up", "scapular pull up", "scapular pullups", "scapular pull ups"],
    },
    {
        "name": "Band Pull-Apart",
        "muscle_group": MuscleGroup.SHOULDERS,
        "is_bodyweight": True,
        "aliases": ["band pull-apart", "band pull apart", "band pull-aparts"],
    },
    {
        "name": "External Rotation",
        "muscle_group": MuscleGroup.SHOULDERS,
        "is_bodyweight": False,
        "aliases": ["external rotation", "external rotations", "rotacje zewnetrzne"],
    },
    {
        "name": "Australian Pull-Up",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["australian pull-up", "australian pull up", "australian pullup"],
    },
    {
        "name": "Half Explosive Pull-Up",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["half explosive pull-up", "half explosive pull up"],
    },
    {
        "name": "Explosive Pull-Up",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["explosive pull-up", "explosive pull up"],
    },
    {
        "name": "High Pull-Up",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["high pull-up", "high pull up", "high pull"],
    },
    {
        "name": "False Grip Hang",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["false grip hang", "false grip"],
    },
    {
        "name": "Assisted Muscle-Up (Band)",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["assisted muscle-up", "assisted muscle up", "muscle-up guma", "muscle up guma"],
    },
    # Trening A
    {
        "name": "Back Squat",
        "muscle_group": MuscleGroup.LEGS,
        "is_bodyweight": False,
        "aliases": ["back squat", "przysiad ze sztanga"],
    },
    {
        "name": "Bench Press",
        "muscle_group": MuscleGroup.CHEST,
        "is_bodyweight": False,
        "aliases": ["bench press", "wyciskanie lezac"],
    },
    {
        "name": "Barbell Row",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": False,
        "aliases": ["barbell row", "pendlay row", "wioslowanie sztanga", "pendlay"],
    },
    {
        "name": "Lateral Raise",
        "muscle_group": MuscleGroup.SHOULDERS,
        "is_bodyweight": False,
        "aliases": ["lateral raise", "lateral raises", "wznosy bokiem"],
    },
    {
        "name": "Dips",
        "muscle_group": MuscleGroup.CHEST,
        "is_bodyweight": True,
        "aliases": ["dips", "pompki na poreczach"],
    },
    {
        "name": "Biceps Curl",
        "muscle_group": MuscleGroup.BICEPS,
        "is_bodyweight": False,
        "aliases": ["biceps curl", "biceps curls", "biceps"],
    },
    {
        "name": "Triceps Extension",
        "muscle_group": MuscleGroup.TRICEPS,
        "is_bodyweight": False,
        "aliases": ["triceps extension", "triceps extensions", "triceps", "prostowanie tricepsa"],
    },
    {
        "name": "Hip Thrust",
        "muscle_group": MuscleGroup.LEGS,
        "is_bodyweight": False,
        "aliases": ["hip thrust", "hip thrusts"],
    },
    {
        "name": "Hollow Hold",
        "muscle_group": MuscleGroup.CORE,
        "is_bodyweight": True,
        "aliases": ["hollow hold", "hollow"],
    },
    {
        "name": "Calf Raise",
        "muscle_group": MuscleGroup.CALVES,
        "is_bodyweight": False,
        "aliases": ["calf raise", "calf raises", "lydki", "wspiecia na palce"],
    },
    {
        "name": "Close Grip Bench Press",
        "muscle_group": MuscleGroup.TRICEPS,
        "is_bodyweight": False,
        "aliases": ["close grip bench press", "wyciskanie wasko"],
    },
    # Trening B
    {
        "name": "Deadlift",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": False,
        "aliases": ["deadlift", "martwy ciag", "martwy ciag klasyczny"],
    },
    {
        "name": "Overhead Press",
        "muscle_group": MuscleGroup.SHOULDERS,
        "is_bodyweight": False,
        "aliases": ["overhead press", "ohp", "wyciskanie zolnierskie", "wyciskanie nad glowe"],
    },
    {
        "name": "Seated Overhead Press",
        "muscle_group": MuscleGroup.SHOULDERS,
        "is_bodyweight": False,
        "aliases": ["seated ohp", "seated overhead press", "wyciskanie siedzac"],
    },
    {
        "name": "Lat Pulldown",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": False,
        "aliases": ["lat pull down", "lat pulldown", "sciaganie drazka"],
    },
    {
        "name": "Seated Cable Row",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": False,
        "aliases": ["seated cable row", "cable row", "wioslowanie na wyciagu siedzac"],
    },
    {
        "name": "Face Pull",
        "muscle_group": MuscleGroup.SHOULDERS,
        "is_bodyweight": False,
        "aliases": ["face pull", "facepull", "face pulls", "przyciaganie linki do twarzy"],
    },
    {
        "name": "Chin-Up",
        "muscle_group": MuscleGroup.BACK,
        "is_bodyweight": True,
        "aliases": ["chin-up", "chin up", "podciaganie wasko", "neutral grip pull-up", "neutral grip pull up"],
    },
    {
        "name": "Plank",
        "muscle_group": MuscleGroup.CORE,
        "is_bodyweight": True,
        "aliases": ["plank", "deska"],
    },
    # Additional
    {
        "name": "Reverse Fly",
        "muscle_group": MuscleGroup.SHOULDERS,
        "is_bodyweight": False,
        "aliases": ["reverse fly", "reverse flye", "odwrotne rozpietki"],
    },
    {
        "name": "Single-Arm Lateral Raise (45 Bench)",
        "muscle_group": MuscleGroup.SHOULDERS,
        "is_bodyweight": False,
        "aliases": [
            "single-arm lateral raise",
            "single arm lateral raise",
            "lateral raise 45",
            "jednoracz lateral raise",
            "jednoracz wznosy bokiem",
            "wznosy bokiem 45",
        ],
    },
    {
        "name": "Single-Arm Landmine Press",
        "muscle_group": MuscleGroup.SHOULDERS,
        "is_bodyweight": False,
        "aliases": [
            "single-arm landmine press",
            "single arm landmine press",
            "landmine press",
            "jednoracz landmine press",
            "jednoracz lateral landmine press",
        ],
    },
]


class Command(BaseCommand):
    help = "Seed a small library of default exercises."

    def handle(self, *args, **options):
        created_count = 0
        alias_count = 0
        for entry in DEFAULT_EXERCISES:
            name = entry["name"]
            muscle_group = entry["muscle_group"]
            is_bodyweight = entry["is_bodyweight"]
            aliases = entry.get("aliases", [])

            normalized_aliases = {normalize_text(alias) for alias in {name, *aliases}}
            existing_alias = (
                ExerciseAlias.objects.select_related("exercise")
                .filter(normalized_alias__in=normalized_aliases)
                .first()
            )

            if existing_alias:
                exercise = existing_alias.exercise
            else:
                slug = slugify(name)
                exercise = Exercise.objects.filter(slug=slug).first()
                if not exercise:
                    exercise = Exercise.objects.filter(name__iexact=name).first()
                if not exercise:
                    exercise = Exercise.objects.create(
                        name=name,
                        slug=slug,
                        primary_muscle_group=muscle_group,
                        is_bodyweight=is_bodyweight,
                    )
                    created_count += 1

            for alias in {name, *aliases}:
                normalized_alias = normalize_text(alias)
                existing = ExerciseAlias.objects.filter(normalized_alias=normalized_alias).first()
                if existing:
                    continue
                ExerciseAlias.objects.create(
                    exercise=exercise,
                    alias=alias,
                    normalized_alias=normalized_alias,
                )
                alias_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete. Created {created_count} exercises and {alias_count} aliases."
            )
        )
