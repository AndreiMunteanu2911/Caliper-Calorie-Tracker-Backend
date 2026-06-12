from functools import lru_cache
from os import getenv

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = "Caliper API"
    api_prefix: str = "/api/v1"
    database_url: str = ""
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    usda_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_app_url: str | None = None
    openrouter_app_name: str | None = None
    cors_origins: tuple[str, ...] = (
        "http://localhost:8081",
        "http://localhost:19006",
    )


@lru_cache
def get_settings() -> Settings:
    configured_origins = getenv("CORS_ORIGINS", "")
    cors_origins = tuple(
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    )
    return Settings(
        database_url=getenv("DATABASE_URL", ""),
        supabase_url=getenv("SUPABASE_URL", ""),
        supabase_jwt_secret=getenv("SUPABASE_JWT_SECRET", ""),
        usda_api_key=getenv("USDA_API_KEY", ""),
        openrouter_api_key=getenv("OPENROUTER_API_KEY", ""),
        openrouter_app_url=getenv("OPENROUTER_APP_URL") or None,
        openrouter_app_name=getenv("OPENROUTER_APP_NAME") or None,
        cors_origins=cors_origins
        or ("http://localhost:8081", "http://localhost:19006"),
    )
