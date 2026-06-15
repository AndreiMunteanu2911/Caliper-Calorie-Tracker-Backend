from datetime import date, datetime

from pydantic import Field

from app.schemas.base import ApiModel


class WeightLogCreate(ApiModel):
    weight_kg: float = Field(ge=20, le=500)
    recorded_on: date


class WeightLogItem(ApiModel):
    id: str
    weight_kg: float
    recorded_on: date
    created_at: datetime


class WeightHistoryResponse(ApiModel):
    entries: list[WeightLogItem]
    latest_weight_kg: float | None
    change_kg: float | None
