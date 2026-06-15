from datetime import date

import asyncpg

from app.core.errors import ResourceNotFoundError
from app.schemas.food import FoodItem
from app.schemas.meal_logs import (
    DashboardResponse,
    MealLogBulkCreate,
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
        external_id=row["external_id"],
        source=row["source"],
        meal_type=row["meal_type"],
        food_name=row["food_name"],
        quantity_g=float(row["quantity_g"]),
        calories=float(row["calories"]),
        protein=float(row["protein"]),
        carbs=float(row["carbs"]),
        fats=float(row["fats"]),
        fiber=float(row["fiber"]),
        sugar=float(row["sugar"]),
        sodium_mg=float(row["sodium_mg"]),
        saturated_fat=float(row["saturated_fat"]),
        logged_at=row["logged_at"],
    )


async def get_dashboard(
    connection: asyncpg.Connection,
    user_id: str,
    timezone: str,
    requested_date: date | None = None,
) -> DashboardResponse:
    validated_timezone = validate_timezone(timezone)
    progress = await get_daily_macro_progress(
        connection,
        user_id,
        validated_timezone,
        requested_date,
    )
    rows = await connection.fetch(
        """
        select id, external_id, source, meal_type, food_name, quantity_g,
               calories, protein, carbs, fats, fiber, sugar, sodium_mg,
               saturated_fat, logged_at
        from public.meal_logs
        where user_id = $1::uuid
          and (logged_at at time zone $2::text)::date =
              coalesce($3::date, (now() at time zone $2::text)::date)
        order by logged_at asc, created_at asc
        """,
        user_id,
        validated_timezone,
        requested_date,
    )
    logged_date_rows = await connection.fetch(
        """
        select distinct (logged_at at time zone $2::text)::date as log_date
        from public.meal_logs
        where user_id = $1::uuid
          and (logged_at at time zone $2::text)::date
              between date_trunc(
                'week',
                coalesce($3::date, (now() at time zone $2::text)::date)::timestamp
              )::date
              and date_trunc(
                'week',
                coalesce($3::date, (now() at time zone $2::text)::date)::timestamp
              )::date + 6
        order by log_date
        """,
        user_id,
        validated_timezone,
        requested_date,
    )
    return DashboardResponse(
        progress=progress,
        logs=[_row_to_item(row) for row in rows],
        logged_dates=[row["log_date"].isoformat() for row in logged_date_rows],
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
          user_id, custom_food_id, external_id, source, meal_type, food_name,
          quantity_g, calories_per_100g, protein_per_100g, carbs_per_100g,
          fats_per_100g, fiber_per_100g, sugar_per_100g,
          sodium_mg_per_100g, saturated_fat_per_100g, calories, protein,
          carbs, fats, fiber, sugar, sodium_mg, saturated_fat, logged_at
        )
        values (
          $1::uuid,
          case when $3 = 'custom' then $2::text::uuid else null end,
          $2::text, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
          $15, $16, $17, $18, $19, $20, $21, $22, coalesce($23, now())
        )
        returning id, external_id, source, meal_type, food_name, quantity_g,
                  calories, protein, carbs, fats, fiber, sugar, sodium_mg,
                  saturated_fat, logged_at
        """,
        user_id,
        food.external_id,
        food.source,
        payload.meal_type.value,
        food.name,
        quantity,
        food.calories,
        food.protein,
        food.carbs,
        food.fats,
        food.fiber,
        food.sugar,
        food.sodium_mg,
        food.saturated_fat,
        _scaled(food.calories, quantity),
        _scaled(food.protein, quantity),
        _scaled(food.carbs, quantity),
        _scaled(food.fats, quantity),
        _scaled(food.fiber, quantity),
        _scaled(food.sugar, quantity),
        _scaled(food.sodium_mg, quantity),
        _scaled(food.saturated_fat, quantity),
        payload.logged_at,
    )
    if row is None:
        raise RuntimeError("Meal log insert returned no row")
    if food.source == "custom":
        await connection.execute(
            """
            update public.custom_foods
            set last_used_at = now()
            where id = $1::uuid and user_id = $2::uuid
            """,
            food.external_id,
            user_id,
        )
    return _row_to_item(row)


async def create_meal_logs_bulk(
    connection: asyncpg.Connection,
    user_id: str,
    payload: MealLogBulkCreate,
) -> list[MealLogItem]:
    async with connection.transaction():
        return [
            await create_meal_log(connection, user_id, item)
            for item in payload.items
        ]


async def update_meal_log(
    connection: asyncpg.Connection,
    user_id: str,
    log_id: str,
    payload: MealLogUpdate,
) -> MealLogItem:
    current = await connection.fetchrow(
        """
        select id, external_id, source, meal_type, food_name, quantity_g,
               calories_per_100g, protein_per_100g, carbs_per_100g,
               fats_per_100g, fiber_per_100g, sugar_per_100g,
               sodium_mg_per_100g, saturated_fat_per_100g, logged_at
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
        set meal_type = $3, quantity_g = $4, calories = $5, protein = $6,
            carbs = $7, fats = $8, fiber = $9, sugar = $10,
            sodium_mg = $11, saturated_fat = $12
        where id = $1::uuid and user_id = $2::uuid
        returning id, external_id, source, meal_type, food_name, quantity_g,
                  calories, protein, carbs, fats, fiber, sugar, sodium_mg,
                  saturated_fat, logged_at
        """,
        log_id,
        user_id,
        payload.meal_type.value if payload.meal_type else current["meal_type"],
        new_quantity,
        _scaled(float(current["calories_per_100g"]), new_quantity),
        _scaled(float(current["protein_per_100g"]), new_quantity),
        _scaled(float(current["carbs_per_100g"]), new_quantity),
        _scaled(float(current["fats_per_100g"]), new_quantity),
        _scaled(float(current["fiber_per_100g"]), new_quantity),
        _scaled(float(current["sugar_per_100g"]), new_quantity),
        _scaled(float(current["sodium_mg_per_100g"]), new_quantity),
        _scaled(float(current["saturated_fat_per_100g"]), new_quantity),
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
