from typing import Literal

from pydantic import Field

from app.schemas.base import ApiModel


class PlateAnalysisRequest(ApiModel):
    image_base64: str = Field(min_length=1, max_length=20_000_000)
    media_type: str = Field(default="image/jpeg", pattern=r"^image/")
    context: str | None = Field(default=None, max_length=500)


class EstimatedFood(ApiModel):
    name: str
    estimated_weight_g: float = Field(ge=0)
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fats: float = Field(ge=0)


class PlateAnalysisResponse(ApiModel):
    foods: list[EstimatedFood]
    total_calories: float = Field(ge=0)
    total_protein: float = Field(ge=0)
    total_carbs: float = Field(ge=0)
    total_fats: float = Field(ge=0)
    confidence_explanation: str


class ChatHistoryItem(ApiModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2_000)


class ChatRequest(ApiModel):
    message: str = Field(min_length=1, max_length=2_000)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=20)


class ChatResponse(ApiModel):
    message: str
