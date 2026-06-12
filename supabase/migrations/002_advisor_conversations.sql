create table public.advisor_conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null default 'Nutrition advisor',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id)
);

create table public.advisor_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.advisor_conversations(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null check (
    length(trim(content)) > 0 and length(content) <= 8000
  ),
  created_at timestamptz not null default now(),
  foreign key (conversation_id, user_id)
    references public.advisor_conversations(id, user_id)
    on delete cascade
);

create unique index advisor_conversations_one_per_user_idx
on public.advisor_conversations (user_id);

create index advisor_messages_conversation_created_idx
on public.advisor_messages (conversation_id, created_at asc);

create trigger advisor_conversations_set_updated_at
before update on public.advisor_conversations
for each row execute function public.set_updated_at();

create or replace function public.touch_advisor_conversation()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.advisor_conversations
  set updated_at = now()
  where id = new.conversation_id;
  return new;
end;
$$;

create trigger advisor_messages_touch_conversation
after insert on public.advisor_messages
for each row execute function public.touch_advisor_conversation();

alter table public.advisor_conversations enable row level security;
alter table public.advisor_messages enable row level security;

create policy "advisor_conversations_select_own"
on public.advisor_conversations for select
using ((select auth.uid()) = user_id);

create policy "advisor_conversations_insert_own"
on public.advisor_conversations for insert
with check ((select auth.uid()) = user_id);

create policy "advisor_conversations_update_own"
on public.advisor_conversations for update
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "advisor_conversations_delete_own"
on public.advisor_conversations for delete
using ((select auth.uid()) = user_id);

create policy "advisor_messages_select_own"
on public.advisor_messages for select
using ((select auth.uid()) = user_id);

create policy "advisor_messages_insert_own"
on public.advisor_messages for insert
with check (
  (select auth.uid()) = user_id
  and role = 'user'
  and exists (
    select 1
    from public.advisor_conversations
    where advisor_conversations.id = conversation_id
      and advisor_conversations.user_id = (select auth.uid())
  )
);

create policy "advisor_messages_delete_own"
on public.advisor_messages for delete
using ((select auth.uid()) = user_id);
