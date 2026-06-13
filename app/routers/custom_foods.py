import asyncpg
from fastapi import APIRouter, Depends, status

from app.core.database import get_database
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.base import ApiModel
from app.schemas.food import FoodItem
from pydantic import Field

router = APIRouter(prefix="/custom-foods", tags=["custom foods"])


class CustomFoodCreate(ApiModel):
    name: str = Field(min_length=1, max_length=300)
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fats: float = Field(ge=0)


@router.get("")
async def list_custom_foods(
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> list[FoodItem]:
    rows = await connection.fetch(
        """
        select id, name, brand, serving_size_g, calories, protein, carbs, fats
        from public.custom_foods
        where user_id = $1::uuid
        order by updated_at desc
        """,
        user.id,
    )
    return [
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
        )
        for row in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_custom_food(
    payload: CustomFoodCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> FoodItem:
    row = await connection.fetchrow(
        """
        insert into public.custom_foods (user_id, name, calories, protein, carbs, fats)
        values ($1::uuid, $2, $3, $4, $5, $6)
        returning id, name, brand, serving_size_g, calories, protein, carbs, fats
        """,
        user.id,
        payload.name,
        payload.calories,
        payload.protein,
        payload.carbs,
        payload.fats,
    )
    if row is None:
        raise RuntimeError("Custom food insert returned no row")
    return FoodItem(
        external_id=str(row["id"]),
        source="custom",
        name=row["name"],
        brand=row.get("brand"),
        serving_size_g=float(row["serving_size_g"]),
        calories=float(row["calories"]),
        protein=float(row["protein"]),
        carbs=float(row["carbs"]),
        fats=float(row["fats"]),
    )


@router.delete("/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_food(
    food_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> None:
    result = await connection.execute(
        "delete from public.custom_foods where id = $1::uuid and user_id = $2::uuid",
        food_id,
        user.id,
    )
    if result != "DELETE 1":
        from app.core.errors import ResourceNotFoundError
        raise ResourceNotFoundError("Custom food")
