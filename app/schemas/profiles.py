from typing import Literal, Self

from pydantic import Field, model_validator

from app.schemas.base import ApiModel


class ProfileResponse(ApiModel):
    display_name: str | None
    email: str
    daily_calorie_target: float
    daily_protein_target: float
    daily_carbs_target: float
    daily_fats_target: float
    protein_percentage: float
    carbs_percentage: float
    fats_percentage: float


class ProfileUpdate(ApiModel):
    display_name: str = Field(min_length=1, max_length=80)
    daily_calorie_target: float = Field(gt=0, le=20_000)
    target_mode: Literal["grams", "percentages"] = "grams"
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fats: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_percentages(self) -> Self:
        if self.target_mode == "percentages":
            total = self.protein + self.carbs + self.fats
            if abs(total - 100) > 0.1:
                raise ValueError("Macro percentages must total 100.")
        return self


class TdeeCalculationRequest(ApiModel):
    sex: Literal["female", "male"]
    age: int = Field(ge=14, le=100)
    height_cm: float = Field(ge=120, le=250)
    weight_kg: float = Field(ge=20, le=500)
    activity_level: Literal[
        "sedentary",
        "light",
        "moderate",
        "very_active",
        "extra_active",
    ]
    goal: Literal["lose", "maintain", "gain"]


class TdeeCalculationResponse(ApiModel):
    bmr: float
    tdee: float
    daily_calorie_target: float
    daily_protein_target: float
    daily_carbs_target: float
    daily_fats_target: float
