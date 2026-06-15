from app.schemas.profiles import TdeeCalculationRequest, TdeeCalculationResponse

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "very_active": 1.725,
    "extra_active": 1.9,
}

GOAL_ADJUSTMENTS = {
    "lose": -500,
    "maintain": 0,
    "gain": 300,
}


def calculate_tdee(payload: TdeeCalculationRequest) -> TdeeCalculationResponse:
    sex_adjustment = 5 if payload.sex == "male" else -161
    bmr = (
        10 * payload.weight_kg
        + 6.25 * payload.height_cm
        - 5 * payload.age
        + sex_adjustment
    )
    tdee = bmr * ACTIVITY_MULTIPLIERS[payload.activity_level]
    calorie_target = max(1200, tdee + GOAL_ADJUSTMENTS[payload.goal])

    protein = calorie_target * 0.3 / 4
    carbs = calorie_target * 0.4 / 4
    fats = calorie_target * 0.3 / 9
    return TdeeCalculationResponse(
        bmr=round(bmr, 2),
        tdee=round(tdee, 2),
        daily_calorie_target=round(calorie_target),
        daily_protein_target=round(protein),
        daily_carbs_target=round(carbs),
        daily_fats_target=round(fats),
    )
