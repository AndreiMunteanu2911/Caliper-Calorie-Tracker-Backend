from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg

from app.core.errors import InputValidationError
from app.schemas.macros import DailyMacroProgress, MacroTotals


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
