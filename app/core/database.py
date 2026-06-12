from collections.abc import AsyncIterator

import asyncpg
from fastapi import Request


async def get_database(request: Request) -> AsyncIterator[asyncpg.Connection]:
    pool: asyncpg.Pool = request.app.state.database_pool
    async with pool.acquire() as connection:
        yield connection
