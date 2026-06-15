create table public.weight_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  weight_kg numeric(6, 2) not null check (weight_kg between 20 and 500),
  recorded_on date not null default current_date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, recorded_on)
);

create index weight_logs_user_recorded_on_idx
  on public.weight_logs (user_id, recorded_on desc);

create trigger weight_logs_set_updated_at
before update on public.weight_logs
for each row execute function public.set_updated_at();

alter table public.weight_logs enable row level security;

create policy "weight_logs_select_own" on public.weight_logs for select
using ((select auth.uid()) = user_id);
create policy "weight_logs_insert_own" on public.weight_logs for insert
with check ((select auth.uid()) = user_id);
create policy "weight_logs_update_own" on public.weight_logs for update
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "weight_logs_delete_own" on public.weight_logs for delete
using ((select auth.uid()) = user_id);
