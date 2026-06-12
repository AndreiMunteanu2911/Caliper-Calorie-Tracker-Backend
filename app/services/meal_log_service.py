import asyncpg

from app.core.errors import ResourceNotFoundError
from app.schemas.food import FoodItem
from app.schemas.meal_logs import (
    DashboardResponse,
    MealLogCreate,
    MealLogItem,
    MealLogUpdate,
)
from app.services.macro_service import get_daily_macro_progress, validate_timezone


def _scaled(value: float, quantity_g: float) -> float:
    return round(value * quantity_g / 100, 2)


def _row_to_item(row: asyncpg.Record) -> MealLogItem:
    return MealLogItem(
        id=str(row["id"]),
        meal_type=row["meal_type"],
        food_name=row["food_name"],
        quantity_g=float(row["quantity_g"]),
        calories=float(row["calories"]),
        protein=float(row["protein"]),
        carbs=float(row["carbs"]),
        fats=float(row["fats"]),
        logged_at=row["logged_at"],
    )


async def get_dashboard(
    connection: asyncpg.Connection,
    user_id: str,
    timezone: str,
) -> DashboardResponse:
    validated_timezone = validate_timezone(timezone)
    progress = await get_daily_macro_progress(
        connection,
        user_id,
        validated_timezone,
    )
    rows = await connection.fetch(
        """
        select id, meal_type, food_name, quantity_g, calories, protein, carbs,
               fats, logged_at
        from public.meal_logs
        where user_id = $1::uuid
          and (logged_at at time zone $2::text)::date =
              (now() at time zone $2::text)::date
        order by logged_at asc, created_at asc
        """,
        user_id,
        validated_timezone,
    )
    return DashboardResponse(
        progress=progress,
        logs=[_row_to_item(row) for row in rows],
    )


async def create_meal_log(
    connection: asyncpg.Connection,
    user_id: str,
    payload: MealLogCreate,
) -> MealLogItem:
    food: FoodItem = payload.food
    quantity = payload.quantity_g
    row = await connection.fetchrow(
        """
        insert into public.meal_logs (
          user_id, meal_type, food_name, quantity_g, calories_per_100g,
          protein_per_100g, carbs_per_100g, fats_per_100g, calories, protein,
          carbs, fats, logged_at
        )
        values (
          $1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
          coalesce($13, now())
        )
        returning id, meal_type, food_name, quantity_g, calories, protein,
                  carbs, fats, logged_at
        """,
        user_id,
        payload.meal_type.value,
        food.name,
        quantity,
        food.calories,
        food.protein,
        food.carbs,
        food.fats,
        _scaled(food.calories, quantity),
        _scaled(food.protein, quantity),
        _scaled(food.carbs, quantity),
        _scaled(food.fats, quantity),
        payload.logged_at,
    )
    if row is None:
        raise RuntimeError("Meal log insert returned no row")
    return _row_to_item(row)


async def update_meal_log(
    connection: asyncpg.Connection,
    user_id: str,
    log_id: str,
    payload: MealLogUpdate,
) -> MealLogItem:
    current = await connection.fetchrow(
        """
        select id, meal_type, food_name, quantity_g, calories_per_100g,
               protein_per_100g, carbs_per_100g, fats_per_100g, calories,
               protein, carbs, fats, logged_at
        from public.meal_logs
        where id = $1::uuid and user_id = $2::uuid
        """,
        log_id,
        user_id,
    )
    if current is None:
        raise ResourceNotFoundError("Meal log")

    new_quantity = payload.quantity_g or float(current["quantity_g"])
    row = await connection.fetchrow(
        """
        update public.meal_logs
        set meal_type = $3,
            quantity_g = $4,
            calories = $5,
            protein = $6,
            carbs = $7,
            fats = $8
        where id = $1::uuid and user_id = $2::uuid
        returning id, meal_type, food_name, quantity_g, calories, protein,
                  carbs, fats, logged_at
        """,
        log_id,
        user_id,
        payload.meal_type.value if payload.meal_type else current["meal_type"],
        new_quantity,
        _scaled(float(current["calories_per_100g"]), new_quantity),
        _scaled(float(current["protein_per_100g"]), new_quantity),
        _scaled(float(current["carbs_per_100g"]), new_quantity),
        _scaled(float(current["fats_per_100g"]), new_quantity),
    )
    if row is None:
        raise ResourceNotFoundError("Meal log")
    return _row_to_item(row)


async def delete_meal_log(
    connection: asyncpg.Connection,
    user_id: str,
    log_id: str,
) -> None:
    result = await connection.execute(
        "delete from public.meal_logs where id = $1::uuid and user_id = $2::uuid",
        log_id,
        user_id,
    )
    if result != "DELETE 1":
        raise ResourceNotFoundError("Meal log")
