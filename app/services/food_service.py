import json
from typing import Any

import httpx

from app.core.errors import (
    ExternalServiceError,
    InputValidationError,
    ResourceNotFoundError,
)
from app.schemas.food import FoodItem

OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product"
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"


def _number(value: object) -> float:
    try:
        return max(float(value or 0), 0)
    except (TypeError, ValueError):
        return 0


async def get_food_by_barcode(
    client: httpx.AsyncClient,
    barcode: str,
) -> FoodItem:
    try:
        response = await client.get(
            f"{OPEN_FOOD_FACTS_URL}/{barcode}.json",
            params={"fields": "code,product_name,brands,nutriments"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ExternalServiceError(
            "Open Food Facts",
            "Barcode lookup is temporarily unavailable.",
        ) from exc
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise ExternalServiceError(
            "Open Food Facts",
            "Barcode lookup returned invalid data.",
        ) from exc
    if not isinstance(payload, dict):
        raise ExternalServiceError(
            "Open Food Facts",
            "Barcode lookup returned invalid data.",
        )
    product = payload.get("product")
    if payload.get("status") != 1 or not isinstance(product, dict):
        raise ResourceNotFoundError("Food")

    nutrients = product.get("nutriments", {})
    if not isinstance(nutrients, dict):
        nutrients = {}
    return FoodItem(
        external_id=str(product.get("code") or barcode),
        source="open_food_facts",
        name=str(product.get("product_name") or "Unknown food"),
        brand=str(product["brands"]) if product.get("brands") else None,
        calories=_number(
            nutrients.get("energy-kcal_100g") or nutrients.get("energy-kcal")
        ),
        protein=_number(nutrients.get("proteins_100g")),
        carbs=_number(nutrients.get("carbohydrates_100g")),
        fats=_number(nutrients.get("fat_100g")),
    )


def _nutrient_value(food: dict[str, Any], nutrient_ids: set[int]) -> float:
    for nutrient in food.get("foodNutrients", []):
        if nutrient.get("nutrientId") in nutrient_ids:
            return _number(nutrient.get("value"))
    return 0


async def search_usda_foods(
    client: httpx.AsyncClient,
    query: str,
    api_key: str,
) -> list[FoodItem]:
    normalized_query = query.strip()
    if len(normalized_query) < 2:
        raise InputValidationError("Search query must contain at least 2 characters.")
    if not api_key:
        raise ExternalServiceError(
            "USDA FoodData Central",
            "USDA_API_KEY is not configured.",
        )
    try:
        response = await client.post(
            USDA_SEARCH_URL,
            params={"api_key": api_key},
            json={
                "query": normalized_query,
                "dataType": ["Foundation", "SR Legacy"],
                "pageSize": 25,
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ExternalServiceError(
            "USDA FoodData Central",
            "Food search is temporarily unavailable.",
        ) from exc

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise ExternalServiceError(
            "USDA FoodData Central",
            "Food search returned invalid data.",
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("foods", []), list):
        raise ExternalServiceError(
            "USDA FoodData Central",
            "Food search returned invalid data.",
        )

    items: list[FoodItem] = []
    for food in payload.get("foods", []):
        if not isinstance(food, dict):
            continue
        items.append(
            FoodItem(
                external_id=str(food.get("fdcId", "")),
                source="usda",
                name=str(food.get("description") or "Unknown food"),
                brand=food.get("brandOwner"),
                calories=_nutrient_value(food, {1008, 2047, 2048}),
                protein=_nutrient_value(food, {1003}),
                carbs=_nutrient_value(food, {1005}),
                fats=_nutrient_value(food, {1004}),
            )
        )
    return items
