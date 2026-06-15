import asyncpg
from fastapi import APIRouter, Depends

from app.core.database import get_database
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.profiles import (
    ProfileResponse,
    ProfileUpdate,
    OnboardingUpdate,
    TdeeCalculationRequest,
    TdeeCalculationResponse,
)
from app.services.profile_service import (
    complete_onboarding,
    get_profile,
    skip_onboarding,
    update_profile,
)
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


@router.post("/onboarding", response_model=ProfileResponse)
async def finish_onboarding(
    update: OnboardingUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> ProfileResponse:
    return await complete_onboarding(
        connection,
        user.id,
        user.email or "",
        update,
    )


@router.post("/onboarding/skip", response_model=ProfileResponse)
async def dismiss_onboarding(
    user: AuthenticatedUser = Depends(get_current_user),
    connection: asyncpg.Connection = Depends(get_database),
) -> ProfileResponse:
    return await skip_onboarding(connection, user.id, user.email or "")
