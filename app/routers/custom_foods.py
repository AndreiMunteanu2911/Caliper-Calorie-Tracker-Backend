from typing import Self
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Response, status
from pydantic import Field, model_validator

from app.core.database import get_database
from app.core.errors import ResourceNotFoundError
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.base import ApiModel
from app.schemas.food import FoodItem

router = APIRouter(prefix="/custom-foods", tags=["custom foods"])


class CustomFoodCreate(ApiModel):
    name: str = Field(min_length=1, max_length=300)
    brand: str | None = Field(default=None, max_length=300)
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fats: float = Field(ge=0)
    fiber: float = Field(default=0, ge=0)
    sugar: float = Field(default=0, ge=0)
    sodium_mg: float = Field(default=0, ge=0)
    saturated_fat: float = Field(default=0, ge=0)


class CustomFoodUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    brand: str | None = Field(default=None, max_length=300)
    calories: float | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbs: float | None = Field(default=None, ge=0)
    fats: float | None = Field(default=None, ge=0)
    fiber: float | None = Field(default=None, ge=0)
    sugar: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)
    saturated_fat: float | None = Field(default=None, ge=0)
    is_favorite: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        return self


def _food(row: asyncpg.Record) -> FoodItem:
    return FoodItem(
        external_id=str(row["id"]),
        source="custom",
        name=row["name"],
        brand=row["brand"],
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


FOOD_COLUMNS = """
id, name, brand, serving_size_g, calories, protein, carbs, fats, fiber,
sugar, sodium_mg, saturated_fat, is_favorite
"""


@router.get("")
async def list_custom_foods(
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> list[FoodItem]:
    rows = await connection.fetch(
        f"""
        select {FOOD_COLUMNS}
        from public.custom_foods
        where user_id = $1::uuid
        order by is_favorite desc, last_used_at desc nulls last, updated_at desc
        """,
        user.id,
    )
    return [_food(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_custom_food(
    payload: CustomFoodCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> FoodItem:
    row = await connection.fetchrow(
        f"""
        insert into public.custom_foods (
          user_id, name, brand, calories, protein, carbs, fats, fiber, sugar,
          sodium_mg, saturated_fat
        )
        values ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        returning {FOOD_COLUMNS}
        """,
        user.id,
        payload.name,
        payload.brand,
        payload.calories,
        payload.protein,
        payload.carbs,
        payload.fats,
        payload.fiber,
        payload.sugar,
        payload.sodium_mg,
        payload.saturated_fat,
    )
    if row is None:
        raise RuntimeError("Custom food insert returned no row")
    return _food(row)


@router.patch("/{food_id}")
async def update_custom_food(
    food_id: UUID,
    payload: CustomFoodUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> FoodItem:
    values = payload.model_dump(exclude_unset=True)
    assignments = []
    arguments: list[object] = [str(food_id), user.id]
    for key, value in values.items():
        arguments.append(value)
        assignments.append(f"{key} = ${len(arguments)}")
    row = await connection.fetchrow(
        f"""
        update public.custom_foods
        set {", ".join(assignments)}
        where id = $1::uuid and user_id = $2::uuid
        returning {FOOD_COLUMNS}
        """,
        *arguments,
    )
    if row is None:
        raise ResourceNotFoundError("Custom food")
    return _food(row)


@router.delete(
    "/{food_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_custom_food(
    food_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> Response:
    result = await connection.execute(
        "delete from public.custom_foods where id = $1::uuid and user_id = $2::uuid",
        str(food_id),
        user.id,
    )
    if result != "DELETE 1":
        raise ResourceNotFoundError("Custom food")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
