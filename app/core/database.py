from collections.abc import AsyncIterator

import asyncpg
from fastapi import Request

from app.core.config import get_settings


async def create_database_pool() -> asyncpg.Pool:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL must be configured")
    return await asyncpg.create_pool(
        settings.database_url,
        min_size=0,
        max_size=5,
        command_timeout=20,
        statement_cache_size=0,
    )


async def get_database(request: Request) -> AsyncIterator[asyncpg.Connection]:
    pool: asyncpg.Pool | None = getattr(
        request.app.state,
        "database_pool",
        None,
    )
    if pool is None:
        pool = await create_database_pool()
        request.app.state.database_pool = pool
    async with pool.acquire() as connection:
        yield connection
