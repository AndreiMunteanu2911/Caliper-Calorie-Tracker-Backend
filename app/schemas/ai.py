from datetime import datetime
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
    fiber: float = Field(default=0, ge=0)
    sugar: float = Field(default=0, ge=0)
    sodium_mg: float = Field(default=0, ge=0)
    saturated_fat: float = Field(default=0, ge=0)


class PlateAnalysisResponse(ApiModel):
    foods: list[EstimatedFood]
    total_calories: float = Field(ge=0)
    total_protein: float = Field(ge=0)
    total_carbs: float = Field(ge=0)
    total_fats: float = Field(ge=0)
    confidence_explanation: str


class NutritionLabelResponse(ApiModel):
    name: str | None = Field(default=None, max_length=300)
    brand: str | None = Field(default=None, max_length=300)
    serving_size_g: float = Field(gt=0)
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fats: float = Field(ge=0)
    fiber: float = Field(default=0, ge=0)
    sugar: float = Field(default=0, ge=0)
    sodium_mg: float = Field(default=0, ge=0)
    saturated_fat: float = Field(default=0, ge=0)
    transcription: str
    confidence_explanation: str


class AdvisorMessage(ApiModel):
    id: str
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)
    created_at: datetime


class AdvisorConversation(ApiModel):
    id: str
    messages: list[AdvisorMessage]


class ChatRequest(ApiModel):
    message: str = Field(min_length=1, max_length=2_000)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    conversation_id: str | None = None


class ChatResponse(ApiModel):
    conversation_id: str
    user_message: AdvisorMessage
    assistant_message: AdvisorMessage
