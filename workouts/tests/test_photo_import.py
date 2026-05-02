from __future__ import annotations

import json
import os
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from workouts.photo_import import (
    WorkoutPhotoImportConfigurationError,
    import_workout_photo,
)
from workouts.models import MuscleGroup
from workouts.tests.factories import create_exercise


class WorkoutPhotoImportServiceTests(TestCase):
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_import_workout_photo_requires_api_key(self) -> None:
        photo = SimpleUploadedFile(
            "workout.jpg",
            b"fake-image",
            content_type="image/jpeg",
        )

        with self.assertRaises(WorkoutPhotoImportConfigurationError):
            import_workout_photo(photo)

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @mock.patch("workouts.photo_import._post_openai_request")
    def test_import_workout_photo_collects_validation_warnings(
        self,
        mock_post_openai_request: mock.Mock,
    ) -> None:
        create_exercise("Bench Press", muscle_group=MuscleGroup.CHEST)
        mock_post_openai_request.return_value = {
            "output_text": json.dumps(
                {
                    "entries": [
                        "3x5 Bench Press 75kg",
                        "3x8 Mystery Row 40kg",
                    ],
                    "warnings": ["Bottom-right note was skipped."],
                }
            )
        }
        photo = SimpleUploadedFile(
            "workout.jpg",
            b"fake-image",
            content_type="image/jpeg",
        )

        result = import_workout_photo(photo)

        self.assertEqual(
            result.entries,
            ["3x5 Bench Press 75kg", "3x8 Mystery Row 40kg"],
        )
        self.assertIn("Bottom-right note was skipped.", result.warnings)
        self.assertIn(
            "3x8 Mystery Row 40kg: Unknown exercise 'Mystery Row'.",
            result.warnings,
        )
