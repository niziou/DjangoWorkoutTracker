from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from django.core.files.uploadedfile import UploadedFile

from .services import parse_entries

OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_RESPONSES_URL = f"{OPENAI_API_BASE.rstrip('/')}/responses"
DEFAULT_OPENAI_MODEL = os.environ.get("OPENAI_WORKOUT_IMPORT_MODEL", "gpt-5.4-mini")
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("OPENAI_WORKOUT_IMPORT_TIMEOUT_SECONDS", "45"))
DEFAULT_MAX_UPLOAD_BYTES = int(os.environ.get("WORKOUT_PHOTO_IMPORT_MAX_BYTES", "8388608"))

PHOTO_IMPORT_PROMPT = """
Extract a workout plan from a notebook photo into line-based training entries.

Return only data that is clearly visible in the image.
Preserve the original exercise order.
Do not invent exercises, weights, reps, or durations.
Use kilograms when weight is visible.

Supported entry styles:
1. Uniform weighted sets: "3x5 bench press 75kg"
2. Uniform timed sets: "3x30s plank"
3. Variable set lists: "bench press: 20kg x 5, 40kg x 5, 60kg x 5"
4. Variable timed sets: "plank: 30s, 30s, 45s"
5. Variable bodyweight reps: "pull up: 8 reps, 7 reps, 6 reps"

If a line is unreadable or cannot be represented safely, skip it from entries and add a short warning.
Keep exercise names concise and normalized.
""".strip()

PHOTO_IMPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {"type": "string"},
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["entries", "warnings"],
    "additionalProperties": False,
}


class WorkoutPhotoImportError(ValueError):
    pass


class WorkoutPhotoImportConfigurationError(WorkoutPhotoImportError):
    pass


class WorkoutPhotoImportProviderError(WorkoutPhotoImportError):
    pass


@dataclass(frozen=True)
class WorkoutPhotoImportResult:
    entries: list[str]
    warnings: list[str]


def import_workout_photo(
    uploaded_file: UploadedFile,
    *,
    model: str | None = None,
) -> WorkoutPhotoImportResult:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise WorkoutPhotoImportConfigurationError(
            "Photo import is not configured. Set OPENAI_API_KEY on the server."
        )

    image_bytes = uploaded_file.read()
    uploaded_file.seek(0)
    if not image_bytes:
        raise WorkoutPhotoImportError("The uploaded photo is empty.")
    if len(image_bytes) > DEFAULT_MAX_UPLOAD_BYTES:
        raise WorkoutPhotoImportError(
            f"The uploaded photo is too large. Max size is {DEFAULT_MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    mime_type = _resolve_mime_type(uploaded_file)
    image_url = _build_data_url(image_bytes, mime_type)
    payload = _build_openai_request_payload(image_url=image_url, model=model or DEFAULT_OPENAI_MODEL)
    response_payload = _post_openai_request(payload=payload, api_key=api_key)
    parsed_payload = _parse_response_payload(response_payload)

    entries = _clean_string_list(parsed_payload.get("entries"))
    warnings = _clean_string_list(parsed_payload.get("warnings"))
    if not entries:
        raise WorkoutPhotoImportError(
            "The photo was read, but no workout entries could be extracted."
        )

    _, validation_errors = parse_entries(entries, allow_create_missing=False)
    warnings = _dedupe_strings([*warnings, *validation_errors])
    return WorkoutPhotoImportResult(entries=entries, warnings=warnings)


def _resolve_mime_type(uploaded_file: UploadedFile) -> str:
    content_type = (uploaded_file.content_type or "").strip().lower()
    if content_type.startswith("image/"):
        return content_type

    guessed_type, _ = mimetypes.guess_type(uploaded_file.name or "")
    if guessed_type and guessed_type.startswith("image/"):
        return guessed_type

    raise WorkoutPhotoImportError("Only image uploads are supported.")


def _build_data_url(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _build_openai_request_payload(*, image_url: str, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": PHOTO_IMPORT_PROMPT,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Extract workout entries from this notebook photo.",
                    },
                    {
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": "high",
                    },
                ],
            }
        ],
        "max_output_tokens": 800,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "workout_photo_import",
                "strict": True,
                "schema": PHOTO_IMPORT_SCHEMA,
            }
        },
    }


def _post_openai_request(*, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request_body = json.dumps(payload).encode("utf-8")
    openai_request = request.Request(
        OPENAI_RESPONSES_URL,
        data=request_body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(
            openai_request,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        ) as response:
            raw_response = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = _extract_http_error_message(exc)
        raise WorkoutPhotoImportProviderError(
            f"Photo import request failed: {detail}"
        ) from exc
    except error.URLError as exc:
        raise WorkoutPhotoImportProviderError(
            "Photo import request failed because the OpenAI API could not be reached."
        ) from exc

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise WorkoutPhotoImportProviderError(
            "Photo import request returned an invalid JSON response."
        ) from exc


def _extract_http_error_message(exc: error.HTTPError) -> str:
    try:
        error_payload = json.loads(exc.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return f"HTTP {exc.code}"

    error_data = error_payload.get("error")
    if isinstance(error_data, dict):
        message = error_data.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return f"HTTP {exc.code}"


def _parse_response_payload(response_payload: dict[str, Any]) -> dict[str, Any]:
    output_text = _extract_output_text(response_payload)
    try:
        parsed_payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise WorkoutPhotoImportProviderError(
            "Photo import returned malformed structured output."
        ) from exc

    if not isinstance(parsed_payload, dict):
        raise WorkoutPhotoImportProviderError(
            "Photo import returned an unexpected response shape."
        )
    return parsed_payload


def _extract_output_text(response_payload: dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for item in response_payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content_item in item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") == "refusal":
                refusal = content_item.get("refusal") or "The model refused the import request."
                raise WorkoutPhotoImportProviderError(str(refusal))
            if content_item.get("type") == "output_text":
                text = content_item.get("text")
                if isinstance(text, str) and text.strip():
                    return text

    raise WorkoutPhotoImportProviderError(
        "Photo import returned no structured output."
    )


def _clean_string_list(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    return [
        item.strip()
        for item in raw_value
        if isinstance(item, str) and item.strip()
    ]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
