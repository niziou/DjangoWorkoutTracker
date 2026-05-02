from __future__ import annotations

from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from workouts.photo_import import (
    WorkoutPhotoImportConfigurationError,
    WorkoutPhotoImportResult,
)
from workouts.tests.factories import create_user


class WorkoutPhotoImportViewTests(TestCase):
    def setUp(self) -> None:
        self.user = create_user("photo-import-user")
        self.client.force_login(self.user)

    @mock.patch("workouts.web_views.import_workout_photo")
    def test_photo_import_view_returns_entries_and_warnings(
        self,
        mock_import_workout_photo: mock.Mock,
    ) -> None:
        mock_import_workout_photo.return_value = WorkoutPhotoImportResult(
            entries=["3x5 Bench Press 75kg"],
            warnings=["Last line was unreadable."],
        )
        photo = SimpleUploadedFile(
            "workout.jpg",
            b"fake-image",
            content_type="image/jpeg",
        )

        response = self.client.post(reverse("workout-import-photo"), {"photo": photo})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "entries": ["3x5 Bench Press 75kg"],
                "warnings": ["Last line was unreadable."],
            },
        )

    def test_photo_import_view_requires_photo(self) -> None:
        response = self.client.post(reverse("workout-import-photo"))

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {"detail": "Photo is required."},
        )

    @mock.patch("workouts.web_views.import_workout_photo")
    def test_photo_import_view_maps_configuration_errors_to_503(
        self,
        mock_import_workout_photo: mock.Mock,
    ) -> None:
        mock_import_workout_photo.side_effect = WorkoutPhotoImportConfigurationError(
            "Photo import is not configured."
        )
        photo = SimpleUploadedFile(
            "workout.jpg",
            b"fake-image",
            content_type="image/jpeg",
        )

        response = self.client.post(reverse("workout-import-photo"), {"photo": photo})

        self.assertEqual(response.status_code, 503)
        self.assertJSONEqual(
            response.content,
            {"detail": "Photo import is not configured."},
        )
