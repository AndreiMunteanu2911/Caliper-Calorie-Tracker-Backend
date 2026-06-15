import asyncpg
from fastapi import APIRouter, Depends

from app.core.database import get_database
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.profiles import (
    ProfileResponse,
    ProfileUpdate,
    TdeeCalculationRequest,
    TdeeCalculationResponse,
)
from app.services.profile_service import get_profile, update_profile
from app.services.tdee_service import calculate_tdee

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/tdee", response_model=TdeeCalculationResponse)
async def tdee(
    payload: TdeeCalculationRequest,
    _: AuthenticatedUser = Depends(get_current_user),
) -> TdeeCalculationResponse:
    return calculate_tdee(payload)


@router.get("", response_model=ProfileResponse)
async def profile(
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> ProfileResponse:
    return await get_profile(connection, user.id, user.email or "")


@router.patch("", response_model=ProfileResponse)
async def edit_profile(
    update: ProfileUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> ProfileResponse:
    return await update_profile(
        connection,
        user.id,
        user.email or "",
        update,
    )
