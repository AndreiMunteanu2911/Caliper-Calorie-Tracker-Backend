import asyncpg

from app.schemas.profiles import (
    OnboardingUpdate,
    ProfileResponse,
    ProfileUpdate,
)
from app.services.tdee_service import calculate_tdee

PROFILE_COLUMNS = """
display_name, daily_calorie_target, daily_protein_target, daily_carbs_target,
daily_fats_target, onboarding_status, sex, age, height_cm, activity_level,
goal, target_weight_kg
"""


def _response(row: asyncpg.Record, email: str) -> ProfileResponse:
    calories = float(row["daily_calorie_target"])
    protein = float(row["daily_protein_target"])
    carbs = float(row["daily_carbs_target"])
    fats = float(row["daily_fats_target"])
    macro_calories = protein * 4 + carbs * 4 + fats * 9
    percentage_base = macro_calories if macro_calories > 0 else calories
    return ProfileResponse(
        display_name=row["display_name"],
        email=email,
        daily_calorie_target=calories,
        daily_protein_target=protein,
        daily_carbs_target=carbs,
        daily_fats_target=fats,
        protein_percentage=(protein * 4 / percentage_base) * 100,
        carbs_percentage=(carbs * 4 / percentage_base) * 100,
        fats_percentage=(fats * 9 / percentage_base) * 100,
        onboarding_status=row["onboarding_status"],
        sex=row["sex"],
        age=row["age"],
        height_cm=float(row["height_cm"]) if row["height_cm"] is not None else None,
        activity_level=row["activity_level"],
        goal=row["goal"],
        target_weight_kg=(
            float(row["target_weight_kg"])
            if row["target_weight_kg"] is not None
            else None
        ),
    )


async def get_profile(
    connection: asyncpg.Connection,
    user_id: str,
    email: str,
) -> ProfileResponse:
    row = await connection.fetchrow(
        f"select {PROFILE_COLUMNS} from public.profiles where id = $1::uuid",
        user_id,
    )
    if row is None:
        raise RuntimeError("Profile could not be found.")
    return _response(row, email)


async def update_profile(
    connection: asyncpg.Connection,
    user_id: str,
    email: str,
    update: ProfileUpdate,
) -> ProfileResponse:
    if update.target_mode == "percentages":
        protein = update.daily_calorie_target * update.protein / 100 / 4
        carbs = update.daily_calorie_target * update.carbs / 100 / 4
        fats = update.daily_calorie_target * update.fats / 100 / 9
    else:
        protein = update.protein
        carbs = update.carbs
        fats = update.fats
    row = await connection.fetchrow(
        f"""
        update public.profiles
        set display_name = $2, daily_calorie_target = $3,
            daily_protein_target = $4, daily_carbs_target = $5,
            daily_fats_target = $6, target_weight_kg = $7
        where id = $1::uuid
        returning {PROFILE_COLUMNS}
        """,
        user_id,
        update.display_name.strip(),
        update.daily_calorie_target,
        protein,
        carbs,
        fats,
        update.target_weight_kg,
    )
    if row is None:
        raise RuntimeError("Profile could not be updated.")
    return _response(row, email)


async def complete_onboarding(
    connection: asyncpg.Connection,
    user_id: str,
    email: str,
    update: OnboardingUpdate,
) -> ProfileResponse:
    targets = calculate_tdee(update)
    async with connection.transaction():
        row = await connection.fetchrow(
            f"""
            update public.profiles
            set display_name = $2, timezone = $3, sex = $4, age = $5,
                height_cm = $6, activity_level = $7, goal = $8,
                target_weight_kg = $9,
                daily_calorie_target = $10, daily_protein_target = $11,
                daily_carbs_target = $12, daily_fats_target = $13,
                onboarding_status = 'completed'
            where id = $1::uuid
            returning {PROFILE_COLUMNS}
            """,
            user_id,
            update.display_name.strip(),
            update.timezone,
            update.sex,
            update.age,
            update.height_cm,
            update.activity_level,
            update.goal,
            update.target_weight_kg,
            targets.daily_calorie_target,
            targets.daily_protein_target,
            targets.daily_carbs_target,
            targets.daily_fats_target,
        )
        await connection.execute(
            """
            insert into public.weight_logs (user_id, weight_kg, recorded_on)
            values ($1::uuid, $2, current_date)
            on conflict (user_id, recorded_on)
            do update set weight_kg = excluded.weight_kg
            """,
            user_id,
            update.weight_kg,
        )
    if row is None:
        raise RuntimeError("Onboarding could not be completed.")
    return _response(row, email)


async def skip_onboarding(
    connection: asyncpg.Connection,
    user_id: str,
    email: str,
) -> ProfileResponse:
    row = await connection.fetchrow(
        f"""
        update public.profiles
        set onboarding_status = 'skipped'
        where id = $1::uuid
        returning {PROFILE_COLUMNS}
        """,
        user_id,
    )
    if row is None:
        raise RuntimeError("Onboarding could not be skipped.")
    return _response(row, email)
