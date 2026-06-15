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
        order by is_favorite desc, last_used_at desc nulls last, updated_at desc
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
    barcode_rows = await connection.fetch(
        """
        with ranked as (
          select external_id, food_name, calories_per_100g,
                 protein_per_100g, carbs_per_100g, fats_per_100g,
                 fiber_per_100g, sugar_per_100g, sodium_mg_per_100g,
                 saturated_fat_per_100g, logged_at,
                 count(*) over (partition by external_id) as use_count,
                 row_number() over (
                   partition by external_id
                   order by logged_at desc, created_at desc
                 ) as row_number
          from public.meal_logs
          where user_id = $1::uuid
            and source = 'open_food_facts'
            and lower(food_name) like lower($2::text)
        )
        select external_id, food_name, calories_per_100g, protein_per_100g,
               carbs_per_100g, fats_per_100g, fiber_per_100g,
               sugar_per_100g, sodium_mg_per_100g,
               saturated_fat_per_100g, use_count,
               logged_at as last_used_at
        from ranked
        where row_number = 1
        order by use_count desc, last_used_at desc
        limit 10
        """,
        user.id,
        f"%{query}%",
    )
    barcode_items = [
        FoodItem(
            external_id=row["external_id"],
            source="open_food_facts",
            name=row["food_name"],
            brand=None,
            calories=float(row["calories_per_100g"]),
            protein=float(row["protein_per_100g"]),
            carbs=float(row["carbs_per_100g"]),
            fats=float(row["fats_per_100g"]),
            fiber=float(row["fiber_per_100g"]),
            sugar=float(row["sugar_per_100g"]),
            sodium_mg=float(row["sodium_mg_per_100g"]),
            saturated_fat=float(row["saturated_fat_per_100g"]),
        )
        for row in barcode_rows
    ]

    async with httpx.AsyncClient(timeout=20) as client:
        usda_items = await search_usda_foods(client, query, settings.usda_api_key)

    return FoodSearchResponse(items=[*custom_items, *barcode_items, *usda_items])
