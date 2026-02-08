from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workouts", "0002_exercisealias_workoutdraft"),
    ]

    operations = [
        migrations.AddField(
            model_name="workoutsession",
            name="training_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("FBW", "FBW"),
                    ("UPPER", "Upper"),
                    ("LOWER", "Lower"),
                    ("PUSH", "Push"),
                    ("PULL", "Pull"),
                    ("LEGS", "Legs"),
                    ("OTHER", "Other"),
                ],
                max_length=20,
            ),
        ),
    ]
