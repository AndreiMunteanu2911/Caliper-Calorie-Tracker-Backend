import asyncpg
import httpx
from fastapi import APIRouter, Depends, Path, Query

from app.core.database import get_database
from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.food import FoodItem, FoodSearchResponse
from app.services.food_service import get_food_by_barcode, search_usda_foods

router = APIRouter(prefix="/food", tags=["food"])


@router.get("/barcode/{barcode}", response_model=FoodItem)
async def barcode_lookup(
    barcode: str = Path(pattern=r"^\d{6,14}$"),
    _: AuthenticatedUser = Depends(get_current_user),
) -> FoodItem:
    async with httpx.AsyncClient(timeout=15) as client:
        return await get_food_by_barcode(client, barcode)


@router.get("/search", response_model=FoodSearchResponse)
async def search_foods(
    query: str = Query(min_length=2, max_length=100),
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    connection: asyncpg.Connection = Depends(get_database),
) -> FoodSearchResponse:
    custom_rows = await connection.fetch(
        """
        select id, name, brand, serving_size_g, calories, protein, carbs, fats,
               fiber, sugar, sodium_mg, saturated_fat, is_favorite
        from public.custom_foods
        where user_id = $1::uuid
          and lower(name) like lower($2::text)
        order by updated_at desc
        limit 10
        """,
        user.id,
        f"%{query}%",
    )
    custom_items = [
        FoodItem(
            external_id=str(row["id"]),
            source="custom",
            name=row["name"],
            brand=row.get("brand"),
            serving_size_g=float(row["serving_size_g"]),
            calories=float(row["calories"]),
            protein=float(row["protein"]),
            carbs=float(row["carbs"]),
            fats=float(row["fats"]),
            fiber=float(row["fiber"]),
            sugar=float(row["sugar"]),
            sodium_mg=float(row["sodium_mg"]),
            saturated_fat=float(row["saturated_fat"]),
            is_favorite=row["is_favorite"],
        )
        for row in custom_rows
    ]

    async with httpx.AsyncClient(timeout=20) as client:
        usda_items = await search_usda_foods(client, query, settings.usda_api_key)

    return FoodSearchResponse(items=[*custom_items, *usda_items])
