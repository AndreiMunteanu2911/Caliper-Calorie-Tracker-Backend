from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.schemas.base import ApiModel
from app.schemas.food import FoodItem
from app.schemas.macros import DailyMacroProgress


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class MealLogCreate(ApiModel):
    food: FoodItem
    meal_type: MealType
    quantity_g: float = Field(gt=0, le=10_000)
    logged_at: datetime | None = None


class MealLogBulkCreate(ApiModel):
    items: list[MealLogCreate] = Field(min_length=1, max_length=50)


class MealLogUpdate(ApiModel):
    meal_type: MealType | None = None
    quantity_g: float | None = Field(default=None, gt=0, le=10_000)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.meal_type is None and self.quantity_g is None:
            raise ValueError("At least one meal log field must be provided.")
        return self


class MealLogItem(ApiModel):
    id: str
    external_id: str
    source: str
    meal_type: MealType
    food_name: str
    quantity_g: float
    calories: float
    protein: float
    carbs: float
    fats: float
    fiber: float
    sugar: float
    sodium_mg: float
    saturated_fat: float
    logged_at: datetime


class DashboardResponse(ApiModel):
    progress: DailyMacroProgress
    logs: list[MealLogItem]
    logged_dates: list[str]
