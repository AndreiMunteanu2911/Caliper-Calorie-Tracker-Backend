-- Remove one-conversation-per-user constraint
drop index if exists public.advisor_conversations_one_per_user_idx;

-- Drop the composite FK (conversation_id, user_id) -> (id, user_id)
alter table public.advisor_messages
  drop constraint if exists advisor_messages_conversation_id_user_id_fkey;

-- Drop the composite unique constraint (id, user_id) — redundant with PK
alter table public.advisor_conversations
  drop constraint if exists advisor_conversations_id_user_id_key;
