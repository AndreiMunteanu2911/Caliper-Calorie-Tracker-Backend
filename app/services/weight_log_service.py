import asyncpg

from app.core.errors import ResourceNotFoundError
from app.schemas.weight_logs import (
    WeightHistoryResponse,
    WeightLogCreate,
    WeightLogItem,
)


def _row_to_item(row: asyncpg.Record) -> WeightLogItem:
    return WeightLogItem(
        id=str(row["id"]),
        weight_kg=float(row["weight_kg"]),
        recorded_on=row["recorded_on"],
        created_at=row["created_at"],
    )


async def get_weight_history(
    connection: asyncpg.Connection,
    user_id: str,
    limit: int,
) -> WeightHistoryResponse:
    rows = await connection.fetch(
        """
        select id, weight_kg, recorded_on, created_at
        from public.weight_logs
        where user_id = $1::uuid
        order by recorded_on desc, created_at desc
        limit $2
        """,
        user_id,
        limit,
    )
    entries = [_row_to_item(row) for row in reversed(rows)]
    latest = entries[-1].weight_kg if entries else None
    change = round(latest - entries[0].weight_kg, 2) if len(entries) > 1 else None
    return WeightHistoryResponse(
        entries=entries,
        latest_weight_kg=latest,
        change_kg=change,
    )


async def upsert_weight_log(
    connection: asyncpg.Connection,
    user_id: str,
    payload: WeightLogCreate,
) -> WeightLogItem:
    row = await connection.fetchrow(
        """
        insert into public.weight_logs (user_id, weight_kg, recorded_on)
        values ($1::uuid, $2, $3)
        on conflict (user_id, recorded_on)
        do update set weight_kg = excluded.weight_kg
        returning id, weight_kg, recorded_on, created_at
        """,
        user_id,
        payload.weight_kg,
        payload.recorded_on,
    )
    if row is None:
        raise RuntimeError("Weight log upsert returned no row.")
    return _row_to_item(row)


async def delete_weight_log(
    connection: asyncpg.Connection,
    user_id: str,
    log_id: str,
) -> None:
    result = await connection.execute(
        "delete from public.weight_logs where id = $1::uuid and user_id = $2::uuid",
        log_id,
        user_id,
    )
    if result != "DELETE 1":
        raise ResourceNotFoundError("Weight log")
