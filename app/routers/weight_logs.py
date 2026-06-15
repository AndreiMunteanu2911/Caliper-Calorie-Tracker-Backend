from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Response, status

from app.core.database import get_database
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.weight_logs import (
    WeightHistoryResponse,
    WeightLogCreate,
    WeightLogItem,
)
from app.services.weight_log_service import (
    delete_weight_log,
    get_weight_history,
    upsert_weight_log,
)

router = APIRouter(prefix="/weight-logs", tags=["weight logs"])


@router.get("", response_model=WeightHistoryResponse)
async def weight_history(
    limit: int = Query(default=90, ge=2, le=365),
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> WeightHistoryResponse:
    return await get_weight_history(connection, user.id, limit)


@router.post(
    "",
    response_model=WeightLogItem,
    status_code=status.HTTP_201_CREATED,
)
async def save_weight(
    payload: WeightLogCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> WeightLogItem:
    return await upsert_weight_log(connection, user.id, payload)


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def remove_weight(
    log_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> Response:
    await delete_weight_log(connection, user.id, str(log_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
