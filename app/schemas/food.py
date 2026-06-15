from pydantic import Field

from app.schemas.base import ApiModel


class FoodItem(ApiModel):
    external_id: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=300)
    brand: str | None = Field(default=None, max_length=300)
    serving_size_g: float = Field(default=100, gt=0)
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fats: float = Field(ge=0)
    fiber: float = Field(default=0, ge=0)
    sugar: float = Field(default=0, ge=0)
    sodium_mg: float = Field(default=0, ge=0)
    saturated_fat: float = Field(default=0, ge=0)
    is_favorite: bool = False


class FoodSearchResponse(ApiModel):
    items: list[FoodItem]
