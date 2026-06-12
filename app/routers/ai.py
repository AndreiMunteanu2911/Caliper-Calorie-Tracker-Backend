import asyncpg
import httpx
from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    PlateAnalysisRequest,
    PlateAnalysisResponse,
)
from app.services.ai_service import analyze_plate, chat_with_advisor
from app.services.macro_service import get_daily_macro_progress

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze-plate", response_model=PlateAnalysisResponse)
async def analyze_plate_image(
    request: PlateAnalysisRequest,
    _: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PlateAnalysisResponse:
    async with httpx.AsyncClient(timeout=60) as client:
        return await analyze_plate(
            client,
            request,
            settings.openrouter_api_key,
            settings.openrouter_app_url,
            settings.openrouter_app_name,
        )


@router.post("/chat", response_model=ChatResponse)
async def advisor_chat(
    request: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    connection: asyncpg.Connection = Depends(get_database),
) -> ChatResponse:
    progress = await get_daily_macro_progress(
        connection,
        user.id,
        request.timezone,
    )

    async with httpx.AsyncClient(timeout=60) as client:
        message = await chat_with_advisor(
            client,
            request.message,
            request.history,
            progress,
            settings.openrouter_api_key,
            settings.openrouter_app_url,
            settings.openrouter_app_name,
        )
    return ChatResponse(message=message)
