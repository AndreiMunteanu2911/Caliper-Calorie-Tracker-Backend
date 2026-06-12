import asyncpg
from fastapi import APIRouter, Depends, Query, Response, status
from uuid import UUID

from app.core.database import get_database
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.meal_logs import (
    DashboardResponse,
    MealLogCreate,
    MealLogItem,
    MealLogUpdate,
)
from app.services.meal_log_service import (
    create_meal_log,
    delete_meal_log,
    get_dashboard,
    update_meal_log,
)

router = APIRouter(tags=["meal logs"])


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    timezone: str = Query(default="UTC", min_length=1, max_length=100),
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> DashboardResponse:
    return await get_dashboard(connection, user.id, timezone)


@router.post(
    "/meal-logs",
    response_model=MealLogItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_log(
    payload: MealLogCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> MealLogItem:
    return await create_meal_log(connection, user.id, payload)


@router.patch("/meal-logs/{log_id}", response_model=MealLogItem)
async def update_log(
    log_id: UUID,
    payload: MealLogUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> MealLogItem:
    return await update_meal_log(connection, user.id, str(log_id), payload)


@router.delete(
    "/meal-logs/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_log(
    log_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> Response:
    await delete_meal_log(connection, user.id, str(log_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
