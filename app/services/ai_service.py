import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.errors import ExternalServiceError
from app.schemas.ai import ChatHistoryItem, PlateAnalysisRequest, PlateAnalysisResponse
from app.schemas.macros import DailyMacroProgress

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

PLATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "foods": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "estimated_weight_g": {"type": "number"},
                    "calories": {"type": "number"},
                    "protein": {"type": "number"},
                    "carbs": {"type": "number"},
                    "fats": {"type": "number"},
                },
                "required": [
                    "name",
                    "estimated_weight_g",
                    "calories",
                    "protein",
                    "carbs",
                    "fats",
                ],
                "additionalProperties": False,
            },
        },
        "total_calories": {"type": "number"},
        "total_protein": {"type": "number"},
        "total_carbs": {"type": "number"},
        "total_fats": {"type": "number"},
        "confidence_explanation": {"type": "string"},
    },
    "required": [
        "foods",
        "total_calories",
        "total_protein",
        "total_carbs",
        "total_fats",
        "confidence_explanation",
    ],
    "additionalProperties": False,
}


def _require_api_key(api_key: str) -> None:
    if not api_key:
        raise ExternalServiceError(
            "OpenRouter",
            "OPENROUTER_API_KEY is not configured.",
        )


def _headers(
    api_key: str,
    app_url: str | None,
    app_name: str | None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if app_url:
        headers["HTTP-Referer"] = app_url
    if app_name:
        headers["X-Title"] = app_name
    return headers


def _extract_json_object(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ExternalServiceError(
        "OpenRouter",
        "The vision model returned an unreadable nutrition estimate.",
    )


def _completion_content(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ExternalServiceError(
            "OpenRouter",
            "The model response did not contain a message.",
        ) from exc
    if isinstance(content, list):
        content = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    if not isinstance(content, str) or not content.strip():
        raise ExternalServiceError(
            "OpenRouter",
            "The model returned an empty response.",
        )
    return content


async def _post_completion(
    client: httpx.AsyncClient,
    api_key: str,
    app_url: str | None,
    app_name: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = await client.post(
            OPENROUTER_URL,
            headers=_headers(api_key, app_url, app_name),
            json=payload,
        )
        response.raise_for_status()
        value = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise ExternalServiceError(
            "OpenRouter",
            "The AI service is temporarily unavailable.",
        ) from exc
    if not isinstance(value, dict):
        raise ExternalServiceError("OpenRouter", "The model returned invalid data.")
    return value


async def analyze_plate(
    client: httpx.AsyncClient,
    request: PlateAnalysisRequest,
    api_key: str,
    app_url: str | None,
    app_name: str | None,
) -> PlateAnalysisResponse:
    _require_api_key(api_key)
    context = request.context or "No additional context was provided."
    payload = await _post_completion(
        client,
        api_key,
        app_url,
        app_name,
        {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a nutrition image analyst. Identify every visible food, "
                        "proactively estimate portion weights when uncertain, and return "
                        "only one JSON object with no markdown or commentary. Macro values "
                        "are grams. The exact required JSON Schema is: "
                        f"{json.dumps(PLATE_SCHEMA, separators=(',', ':'))}"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Meal context: {context}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:{request.media_type};base64,"
                                    f"{request.image_base64}"
                                )
                            },
                        },
                    ],
                },
            ],
        },
    )
    try:
        return PlateAnalysisResponse.model_validate(
            _extract_json_object(_completion_content(payload))
        )
    except ValidationError as exc:
        raise ExternalServiceError(
            "OpenRouter",
            "The vision model returned an incomplete nutrition estimate.",
        ) from exc


async def chat_with_advisor(
    client: httpx.AsyncClient,
    message: str,
    history: list[ChatHistoryItem],
    progress: DailyMacroProgress,
    api_key: str,
    app_url: str | None,
    app_name: str | None,
) -> str:
    _require_api_key(api_key)
    payload = await _post_completion(
        client,
        api_key,
        app_url,
        app_name,
        {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a practical hypertrophy and sports nutrition advisor. "
                        "Use the user's live daily progress below. Do not diagnose medical "
                        "conditions. Give concise, actionable guidance.\n"
                        f"Date: {progress.date} ({progress.timezone})\n"
                        f"Remaining calories: {progress.remaining.calories:.0f} kcal\n"
                        f"Protein needed: {progress.remaining.protein:.1f} g\n"
                        f"Carbs remaining: {progress.remaining.carbs:.1f} g\n"
                        f"Fats remaining: {progress.remaining.fats:.1f} g"
                    ),
                },
                *[
                    {"role": item.role, "content": item.content}
                    for item in history[-20:]
                ],
                {"role": "user", "content": message},
            ],
        },
    )
    return _completion_content(payload)
