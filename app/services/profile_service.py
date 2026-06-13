import asyncpg

from app.schemas.profiles import ProfileResponse, ProfileUpdate


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
    )


async def get_profile(
    connection: asyncpg.Connection,
    user_id: str,
    email: str,
) -> ProfileResponse:
    row = await connection.fetchrow(
        """
        select display_name, daily_calorie_target, daily_protein_target,
               daily_carbs_target, daily_fats_target
        from public.profiles
        where id = $1::uuid
        """,
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
        """
        update public.profiles
        set display_name = $2,
            daily_calorie_target = $3,
            daily_protein_target = $4,
            daily_carbs_target = $5,
            daily_fats_target = $6
        where id = $1::uuid
        returning display_name, daily_calorie_target, daily_protein_target,
                  daily_carbs_target, daily_fats_target
        """,
        user_id,
        update.display_name.strip(),
        update.daily_calorie_target,
        protein,
        carbs,
        fats,
    )
    if row is None:
        raise RuntimeError("Profile could not be updated.")
    return _response(row, email)
