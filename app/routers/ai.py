import json
import logging

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.ai import (
    AdvisorConversation,
    ChatRequest,
    ChatResponse,
    PlateAnalysisRequest,
    PlateAnalysisResponse,
)
from app.services.advisor_service import (
    create_conversation,
    get_conversation,
    get_nutrition_context,
    get_or_create_conversation,
    get_recent_messages,
    list_conversations,
    save_exchange,
)
from app.services.ai_service import analyze_plate, chat_with_advisor, stream_advisor_chat
from app.services.macro_service import get_daily_macro_progress

router = APIRouter(prefix="/ai", tags=["ai"])
logger = logging.getLogger("caliper.ai")


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


@router.get("/conversations")
async def advisor_conversations(
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> list[dict[str, object]]:
    return await list_conversations(connection, user.id)


@router.post("/conversations")
async def new_conversation(
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> dict[str, str]:
    conversation_id = await create_conversation(connection, user.id)
    return {"id": conversation_id}


@router.get("/chat", response_model=AdvisorConversation)
async def advisor_history(
    conversation_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> AdvisorConversation:
    return await get_conversation(connection, user.id, conversation_id)


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
    conversation_id = request.conversation_id or await get_or_create_conversation(connection, user.id)
    history = await get_recent_messages(
        connection,
        conversation_id,
        user.id,
    )
    today_meals, history_summary = await get_nutrition_context(
        connection,
        user.id,
        request.timezone,
    )

    async with httpx.AsyncClient(timeout=60) as client:
        assistant_content = await chat_with_advisor(
            client,
            request.message,
            history,
            progress,
            today_meals,
            history_summary,
            settings.openrouter_api_key,
            settings.openrouter_app_url,
            settings.openrouter_app_name,
        )
    user_message, assistant_message = await save_exchange(
        connection,
        conversation_id,
        user.id,
        request.message,
        assistant_content,
    )
    return ChatResponse(
        conversation_id=conversation_id,
        user_message=user_message,
        assistant_message=assistant_message,
    )


@router.post("/chat/stream")
async def advisor_chat_stream(
    request: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    connection: asyncpg.Connection = Depends(get_database),
) -> StreamingResponse:
    progress = await get_daily_macro_progress(
        connection,
        user.id,
        request.timezone,
    )
    conversation_id = request.conversation_id or await get_or_create_conversation(connection, user.id)
    history = await get_recent_messages(connection, conversation_id, user.id)
    today_meals, history_summary = await get_nutrition_context(
        connection,
        user.id,
        request.timezone,
    )

    async def events():
        chunks: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                async for chunk in stream_advisor_chat(
                    client,
                    request.message,
                    history,
                    progress,
                    today_meals,
                    history_summary,
                    settings.openrouter_api_key,
                    settings.openrouter_app_url,
                    settings.openrouter_app_name,
                ):
                    chunks.append(chunk)
                    yield json.dumps({"type": "delta", "content": chunk}) + "\n"

            assistant_content = "".join(chunks).strip()
            if not assistant_content:
                raise RuntimeError("The AI service returned an empty response.")
            user_message, assistant_message = await save_exchange(
                connection,
                conversation_id,
                user.id,
                request.message,
                assistant_content,
            )
            yield (
                json.dumps(
                    {
                        "type": "done",
                        "conversation_id": conversation_id,
                        "user_message": user_message.model_dump(mode="json"),
                        "assistant_message": assistant_message.model_dump(mode="json"),
                    }
                )
                + "\n"
            )
        except Exception as exc:
            logger.error(
                "Advisor stream failed",
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            yield json.dumps(
                {
                    "type": "error",
                    "code": "advisor_stream_failed",
                    "message": "The advisor is temporarily unavailable. Please try again.",
                }
            ) + "\n"

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
