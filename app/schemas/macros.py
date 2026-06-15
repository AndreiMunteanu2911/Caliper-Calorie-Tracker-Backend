from pydantic import Field

from app.schemas.base import ApiModel


class MacroTotals(ApiModel):
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fats: float = Field(ge=0)


class DailyMacroProgress(ApiModel):
    date: str
    timezone: str
    consumed: MacroTotals
    targets: MacroTotals
    remaining: MacroTotals


class MacroHistoryEntry(ApiModel):
    date: str
    consumed: MacroTotals


class MacroHistoryResponse(ApiModel):
    days: int
    timezone: str
    entries: list[MacroHistoryEntry]
    targets: MacroTotals
