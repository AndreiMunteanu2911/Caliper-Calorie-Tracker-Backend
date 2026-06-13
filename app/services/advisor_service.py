from dataclasses import dataclass

import asyncpg

from app.schemas.ai import AdvisorConversation, AdvisorMessage
from app.services.macro_service import validate_timezone


@dataclass(frozen=True, slots=True)
class TodayMeal:
    meal_type: str
    food_name: str
    quantity_g: float
    calories: float
    protein: float
    carbs: float
    fats: float


@dataclass(frozen=True, slots=True)
class NutritionHistorySummary:
    calendar_days: int
    logged_days: int
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fats: float

    @property
    def average_calories(self) -> float:
        return self.total_calories / self.calendar_days

    @property
    def average_protein(self) -> float:
        return self.total_protein / self.calendar_days

    @property
    def average_carbs(self) -> float:
        return self.total_carbs / self.calendar_days

    @property
    def average_fats(self) -> float:
        return self.total_fats / self.calendar_days


def _message_from_row(row: asyncpg.Record) -> AdvisorMessage:
    return AdvisorMessage(
        id=str(row["id"]),
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
    )


async def get_or_create_conversation(
    connection: asyncpg.Connection,
    user_id: str,
) -> str:
    conversation_id = await connection.fetchval(
        """
        insert into public.advisor_conversations (user_id)
        values ($1::uuid)
        returning id
        """,
        user_id,
    )
    if conversation_id is None:
        raise RuntimeError("Advisor conversation could not be created")
    return str(conversation_id)


async def create_conversation(
    connection: asyncpg.Connection,
    user_id: str,
) -> str:
    conversation_id = await connection.fetchval(
        """
        insert into public.advisor_conversations (user_id)
        values ($1::uuid)
        returning id
        """,
        user_id,
    )
    if conversation_id is None:
        raise RuntimeError("Advisor conversation could not be created")
    return str(conversation_id)


async def list_conversations(
    connection: asyncpg.Connection,
    user_id: str,
) -> list[dict[str, object]]:
    rows = await connection.fetch(
        """
        select id, title, created_at, updated_at
        from public.advisor_conversations
        where user_id = $1::uuid
        order by updated_at desc
        limit 50
        """,
        user_id,
    )
    return [
        {
            "id": str(row["id"]),
            "title": row["title"] or f"Conversation {i + 1}",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for i, row in enumerate(rows)
    ]


async def get_conversation(
    connection: asyncpg.Connection,
    user_id: str,
    conversation_id: str | None = None,
) -> AdvisorConversation:
    if conversation_id is None:
        conversation_id = await connection.fetchval(
            """
            select id from public.advisor_conversations
            where user_id = $1::uuid
            order by updated_at desc
            limit 1
            """,
            user_id,
        )
        if conversation_id is None:
            return AdvisorConversation(id="", messages=[])
        conversation_id = str(conversation_id)
    rows = await connection.fetch(
        """
        select id, role, content, created_at
        from (
          select id, role, content, created_at
          from public.advisor_messages
          where conversation_id = $1::uuid and user_id = $2::uuid
          order by created_at desc, id desc
          limit 200
        ) recent
        order by created_at asc,
                 case role when 'user' then 0 else 1 end,
                 id asc
        """,
        conversation_id,
        user_id,
    )
    return AdvisorConversation(
        id=str(conversation_id),
        messages=[_message_from_row(row) for row in rows],
    )


async def get_recent_messages(
    connection: asyncpg.Connection,
    conversation_id: str,
    user_id: str,
    limit: int = 20,
) -> list[AdvisorMessage]:
    rows = await connection.fetch(
        """
        select id, role, content, created_at
        from (
          select id, role, content, created_at
          from public.advisor_messages
          where conversation_id = $1::uuid and user_id = $2::uuid
          order by created_at desc, id desc
          limit $3
        ) recent
        order by created_at asc,
                 case role when 'user' then 0 else 1 end,
                 id asc
        """,
        conversation_id,
        user_id,
        limit,
    )
    return [_message_from_row(row) for row in rows]


async def get_nutrition_context(
    connection: asyncpg.Connection,
    user_id: str,
    timezone: str,
    calendar_days: int = 30,
) -> tuple[list[TodayMeal], NutritionHistorySummary]:
    validated_timezone = validate_timezone(timezone)
    today_rows = await connection.fetch(
        """
        select meal_type, food_name, quantity_g, calories, protein, carbs, fats
        from public.meal_logs
        where user_id = $1::uuid
          and (logged_at at time zone $2::text)::date =
              (now() at time zone $2::text)::date
        order by logged_at asc, created_at asc
        """,
        user_id,
        validated_timezone,
    )
    summary_row = await connection.fetchrow(
        """
        select
          count(distinct (logged_at at time zone $2::text)::date) as logged_days,
          coalesce(sum(calories), 0) as total_calories,
          coalesce(sum(protein), 0) as total_protein,
          coalesce(sum(carbs), 0) as total_carbs,
          coalesce(sum(fats), 0) as total_fats
        from public.meal_logs
        where user_id = $1::uuid
          and (logged_at at time zone $2::text)::date
            between (now() at time zone $2::text)::date - ($3::int - 1)
                and (now() at time zone $2::text)::date
        """,
        user_id,
        validated_timezone,
        calendar_days,
    )
    if summary_row is None:
        raise RuntimeError("Nutrition history query returned no data")

    meals = [
        TodayMeal(
            meal_type=row["meal_type"],
            food_name=row["food_name"],
            quantity_g=float(row["quantity_g"]),
            calories=float(row["calories"]),
            protein=float(row["protein"]),
            carbs=float(row["carbs"]),
            fats=float(row["fats"]),
        )
        for row in today_rows
    ]
    summary = NutritionHistorySummary(
        calendar_days=calendar_days,
        logged_days=int(summary_row["logged_days"]),
        total_calories=float(summary_row["total_calories"]),
        total_protein=float(summary_row["total_protein"]),
        total_carbs=float(summary_row["total_carbs"]),
        total_fats=float(summary_row["total_fats"]),
    )
    return meals, summary


async def save_exchange(
    connection: asyncpg.Connection,
    conversation_id: str,
    user_id: str,
    user_content: str,
    assistant_content: str,
) -> tuple[AdvisorMessage, AdvisorMessage]:
    if len(assistant_content) > 8_000:
        assistant_content = assistant_content[:8_000].rstrip()
    async with connection.transaction():
        is_first = await connection.fetchval(
            "select count(*) = 0 from public.advisor_messages where conversation_id = $1::uuid",
            conversation_id,
        )
        rows = await connection.fetch(
            """
            insert into public.advisor_messages (
              conversation_id, user_id, role, content
            )
            values
              ($1::uuid, $2::uuid, 'user', $3),
              ($1::uuid, $2::uuid, 'assistant', $4)
            returning id, role, content, created_at
            """,
            conversation_id,
            user_id,
            user_content,
            assistant_content,
        )
        if is_first:
            title = user_content[:60].strip()
            if len(user_content) > 60:
                title += "..."
            await connection.execute(
                "update public.advisor_conversations set title = $1 where id = $2::uuid",
                title,
                conversation_id,
            )
    messages = [_message_from_row(row) for row in rows]
    user_message = next(message for message in messages if message.role == "user")
    assistant_message = next(
        message for message in messages if message.role == "assistant"
    )
    return user_message, assistant_message
