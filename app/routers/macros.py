import asyncpg
from fastapi import APIRouter, Depends, Query

from app.core.database import get_database
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.macros import DailyMacroProgress, MacroHistoryResponse
from app.services.macro_service import get_daily_macro_progress, get_macro_history

router = APIRouter(prefix="/macros", tags=["macros"])


@router.get("/daily", response_model=DailyMacroProgress)
async def daily_progress(
    timezone: str = Query(default="UTC", min_length=1, max_length=100),
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> DailyMacroProgress:
    return await get_daily_macro_progress(connection, user.id, timezone)


@router.get("/history", response_model=MacroHistoryResponse)
async def macro_history(
    days: int = Query(default=7, ge=1, le=90),
    timezone: str = Query(default="UTC", min_length=1, max_length=100),
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> MacroHistoryResponse:
    return await get_macro_history(connection, user.id, timezone, days)
