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


async def get_daily_macro_progress(
    connection: asyncpg.Connection,
    user_id: str,
    timezone: str,
) -> DailyMacroProgress:
    validated_timezone = validate_timezone(timezone)
    row = await connection.fetchrow(
        "select * from public.get_daily_macro_progress($1::uuid, $2::text)",
        user_id,
        validated_timezone,
    )
    if row is None:
        raise RuntimeError("Daily macro progress query returned no data")

    consumed = MacroTotals(
        calories=float(row["calories_consumed"]),
        protein=float(row["protein_consumed"]),
        carbs=float(row["carbs_consumed"]),
        fats=float(row["fats_consumed"]),
    )
    targets = MacroTotals(
        calories=float(row["calorie_target"]),
        protein=float(row["protein_target"]),
        carbs=float(row["carbs_target"]),
        fats=float(row["fats_target"]),
    )
    return DailyMacroProgress(
        date=row["progress_date"].isoformat()
        if isinstance(row["progress_date"], date)
        else str(row["progress_date"]),
        timezone=validated_timezone,
        consumed=consumed,
        targets=targets,
        remaining=MacroTotals(
            calories=max(targets.calories - consumed.calories, 0),
            protein=max(targets.protein - consumed.protein, 0),
            carbs=max(targets.carbs - consumed.carbs, 0),
            fats=max(targets.fats - consumed.fats, 0),
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
            coalesce(sum(fats), 0) as total_fats
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
            date=row["log_date"].isoformat()
            if isinstance(row["log_date"], date)
            else str(row["log_date"]),
            consumed=MacroTotals(
                calories=float(row["total_calories"]),
                protein=float(row["total_protein"]),
                carbs=float(row["total_carbs"]),
                fats=float(row["total_fats"]),
            ),
        )
        for row in rows
    ]

    target_row = await connection.fetchrow(
        """
        select
            daily_calorie_target,
            daily_protein_target,
            daily_carbs_target,
            daily_fats_target
        from public.profiles
        where user_id = $1::uuid
        """,
        user_id,
    )

    if target_row is None:
        raise RuntimeError("User profile not found")

    targets = MacroTotals(
        calories=float(target_row["daily_calorie_target"]),
        protein=float(target_row["daily_protein_target"]),
        carbs=float(target_row["daily_carbs_target"]),
        fats=float(target_row["daily_fats_target"]),
    )

    return MacroHistoryResponse(
        days=days,
        timezone=validated_timezone,
        entries=entries,
        targets=targets,
    )
