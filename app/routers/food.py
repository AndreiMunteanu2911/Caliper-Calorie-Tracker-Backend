import httpx
from fastapi import APIRouter, Depends, Path, Query

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.food import FoodItem, FoodSearchResponse
from app.services.food_service import get_food_by_barcode, search_usda_foods

router = APIRouter(prefix="/food", tags=["food"])


@router.get("/barcode/{barcode}", response_model=FoodItem)
async def barcode_lookup(
    barcode: str = Path(pattern=r"^\d{6,14}$"),
    _: AuthenticatedUser = Depends(get_current_user),
) -> FoodItem:
    async with httpx.AsyncClient(timeout=15) as client:
        return await get_food_by_barcode(client, barcode)


@router.get("/search", response_model=FoodSearchResponse)
async def search_foods(
    query: str = Query(min_length=2, max_length=100),
    _: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> FoodSearchResponse:
    async with httpx.AsyncClient(timeout=20) as client:
        items = await search_usda_foods(client, query, settings.usda_api_key)
    return FoodSearchResponse(items=items)
