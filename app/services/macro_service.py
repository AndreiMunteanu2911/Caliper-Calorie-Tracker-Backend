from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg

from app.core.errors import InputValidationError
from app.schemas.macros import (
    DailyMacroProgress,
    MacroHistoryEntry,
    MacroHistoryResponse,
    MacroTotals,
)


def validate_timezone(timezone: str) -> str:
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise InputValidationError("Unknown IANA timezone.") from exc
    return timezone


def _targets(row: asyncpg.Record) -> MacroTotals:
    return MacroTotals(
        calories=float(row["daily_calorie_target"]),
        protein=float(row["daily_protein_target"]),
        carbs=float(row["daily_carbs_target"]),
        fats=float(row["daily_fats_target"]),
        fiber=0,
        sugar=0,
        sodium_mg=0,
        saturated_fat=0,
    )


async def get_daily_macro_progress(
    connection: asyncpg.Connection,
    user_id: str,
    timezone: str,
    requested_date: date | None = None,
) -> DailyMacroProgress:
    validated_timezone = validate_timezone(timezone)
    row = await connection.fetchrow(
        """
        select
          coalesce($3::date, (now() at time zone $2::text)::date) as progress_date,
          coalesce(sum(meal_logs.calories), 0) as calories_consumed,
          coalesce(sum(meal_logs.protein), 0) as protein_consumed,
          coalesce(sum(meal_logs.carbs), 0) as carbs_consumed,
          coalesce(sum(meal_logs.fats), 0) as fats_consumed,
          coalesce(sum(meal_logs.fiber), 0) as fiber_consumed,
          coalesce(sum(meal_logs.sugar), 0) as sugar_consumed,
          coalesce(sum(meal_logs.sodium_mg), 0) as sodium_consumed,
          coalesce(sum(meal_logs.saturated_fat), 0) as saturated_fat_consumed,
          profiles.daily_calorie_target,
          profiles.daily_protein_target,
          profiles.daily_carbs_target,
          profiles.daily_fats_target
        from public.profiles
        left join public.meal_logs
          on meal_logs.user_id = profiles.id
          and (meal_logs.logged_at at time zone $2::text)::date =
              coalesce($3::date, (now() at time zone $2::text)::date)
        where profiles.id = $1::uuid
        group by profiles.daily_calorie_target, profiles.daily_protein_target,
                 profiles.daily_carbs_target, profiles.daily_fats_target
        """,
        user_id,
        validated_timezone,
        requested_date,
    )
    if row is None:
        raise RuntimeError("Daily macro progress query returned no data")

    consumed = MacroTotals(
        calories=float(row["calories_consumed"]),
        protein=float(row["protein_consumed"]),
        carbs=float(row["carbs_consumed"]),
        fats=float(row["fats_consumed"]),
        fiber=float(row["fiber_consumed"]),
        sugar=float(row["sugar_consumed"]),
        sodium_mg=float(row["sodium_consumed"]),
        saturated_fat=float(row["saturated_fat_consumed"]),
    )
    targets = _targets(row)
    return DailyMacroProgress(
        date=row["progress_date"].isoformat(),
        timezone=validated_timezone,
        consumed=consumed,
        targets=targets,
        remaining=MacroTotals(
            calories=max(targets.calories - consumed.calories, 0),
            protein=max(targets.protein - consumed.protein, 0),
            carbs=max(targets.carbs - consumed.carbs, 0),
            fats=max(targets.fats - consumed.fats, 0),
            fiber=max(targets.fiber - consumed.fiber, 0),
            sugar=max(targets.sugar - consumed.sugar, 0),
            sodium_mg=max(targets.sodium_mg - consumed.sodium_mg, 0),
            saturated_fat=max(
                targets.saturated_fat - consumed.saturated_fat,
                0,
            ),
        ),
    )


async def get_macro_history(
    connection: asyncpg.Connection,
    user_id: str,
    timezone: str,
    days: int,
) -> MacroHistoryResponse:
    validated_timezone = validate_timezone(timezone)
    rows = await connection.fetch(
        """
        select
            (logged_at at time zone $2::text)::date as log_date,
            coalesce(sum(calories), 0) as total_calories,
            coalesce(sum(protein), 0) as total_protein,
            coalesce(sum(carbs), 0) as total_carbs,
            coalesce(sum(fats), 0) as total_fats,
            coalesce(sum(fiber), 0) as total_fiber,
            coalesce(sum(sugar), 0) as total_sugar,
            coalesce(sum(sodium_mg), 0) as total_sodium,
            coalesce(sum(saturated_fat), 0) as total_saturated_fat
        from public.meal_logs
        where user_id = $1::uuid
            and (logged_at at time zone $2::text)::date
                between (now() at time zone $2::text)::date - ($3::int - 1)
                    and (now() at time zone $2::text)::date
        group by log_date
        order by log_date asc
        """,
        user_id,
        validated_timezone,
        days,
    )
    entries = [
        MacroHistoryEntry(
            date=row["log_date"].isoformat(),
            consumed=MacroTotals(
                calories=float(row["total_calories"]),
                protein=float(row["total_protein"]),
                carbs=float(row["total_carbs"]),
                fats=float(row["total_fats"]),
                fiber=float(row["total_fiber"]),
                sugar=float(row["total_sugar"]),
                sodium_mg=float(row["total_sodium"]),
                saturated_fat=float(row["total_saturated_fat"]),
            ),
        )
        for row in rows
    ]
    target_row = await connection.fetchrow(
        """
        select daily_calorie_target, daily_protein_target,
               daily_carbs_target, daily_fats_target
        from public.profiles
        where user_id = $1::uuid
        """,
        user_id,
    )
    if target_row is None:
        raise RuntimeError("User profile not found")
    return MacroHistoryResponse(
        days=days,
        timezone=validated_timezone,
        entries=entries,
        targets=_targets(target_row),
    )
