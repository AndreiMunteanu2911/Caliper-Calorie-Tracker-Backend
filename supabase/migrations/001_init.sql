create extension if not exists pgcrypto;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  user_id uuid not null unique references auth.users(id) on delete cascade,
  display_name text,
  timezone text not null default 'UTC',
  daily_calorie_target numeric(8, 2) not null default 2200 check (daily_calorie_target > 0),
  daily_protein_target numeric(8, 2) not null default 160 check (daily_protein_target >= 0),
  daily_carbs_target numeric(8, 2) not null default 240 check (daily_carbs_target >= 0),
  daily_fats_target numeric(8, 2) not null default 70 check (daily_fats_target >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_identity_matches check (id = user_id)
);

create table public.custom_foods (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  name text not null check (length(trim(name)) > 0),
  brand text,
  serving_size_g numeric(8, 2) not null default 100 check (serving_size_g > 0),
  calories numeric(8, 2) not null check (calories >= 0),
  protein numeric(8, 2) not null default 0 check (protein >= 0),
  carbs numeric(8, 2) not null default 0 check (carbs >= 0),
  fats numeric(8, 2) not null default 0 check (fats >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.meal_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  custom_food_id uuid references public.custom_foods(id) on delete set null,
  meal_type text not null check (meal_type in ('breakfast', 'lunch', 'dinner', 'snack')),
  food_name text not null check (length(trim(food_name)) > 0),
  quantity_g numeric(8, 2) not null check (quantity_g > 0),
  calories_per_100g numeric(8, 2) not null check (calories_per_100g >= 0),
  protein_per_100g numeric(8, 2) not null default 0 check (protein_per_100g >= 0),
  carbs_per_100g numeric(8, 2) not null default 0 check (carbs_per_100g >= 0),
  fats_per_100g numeric(8, 2) not null default 0 check (fats_per_100g >= 0),
  calories numeric(8, 2) not null check (calories >= 0),
  protein numeric(8, 2) not null default 0 check (protein >= 0),
  carbs numeric(8, 2) not null default 0 check (carbs >= 0),
  fats numeric(8, 2) not null default 0 check (fats >= 0),
  logged_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index meal_logs_user_logged_at_idx on public.meal_logs (user_id, logged_at desc);
create index custom_foods_user_name_idx on public.custom_foods (user_id, name);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create trigger custom_foods_set_updated_at
before update on public.custom_foods
for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, user_id, display_name)
  values (new.id, new.id, new.raw_user_meta_data ->> 'display_name');
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

create or replace function public.get_daily_macro_progress(
  requested_user_id uuid,
  requested_timezone text
)
returns table (
  progress_date date,
  calories_consumed numeric,
  protein_consumed numeric,
  carbs_consumed numeric,
  fats_consumed numeric,
  calorie_target numeric,
  protein_target numeric,
  carbs_target numeric,
  fats_target numeric
)
language sql
stable
security invoker
set search_path = ''
as $$
  select
    (now() at time zone requested_timezone)::date as progress_date,
    coalesce(sum(meal_logs.calories), 0) as calories_consumed,
    coalesce(sum(meal_logs.protein), 0) as protein_consumed,
    coalesce(sum(meal_logs.carbs), 0) as carbs_consumed,
    coalesce(sum(meal_logs.fats), 0) as fats_consumed,
    profiles.daily_calorie_target,
    profiles.daily_protein_target,
    profiles.daily_carbs_target,
    profiles.daily_fats_target
  from public.profiles
  left join public.meal_logs
    on meal_logs.user_id = profiles.id
    and (meal_logs.logged_at at time zone requested_timezone)::date =
      (now() at time zone requested_timezone)::date
  where profiles.id = requested_user_id
  group by
    profiles.daily_calorie_target,
    profiles.daily_protein_target,
    profiles.daily_carbs_target,
    profiles.daily_fats_target;
$$;

alter table public.profiles enable row level security;
alter table public.custom_foods enable row level security;
alter table public.meal_logs enable row level security;

create policy "profiles_select_own" on public.profiles for select
using ((select auth.uid()) = user_id);
create policy "profiles_insert_own" on public.profiles for insert
with check ((select auth.uid()) = user_id);
create policy "profiles_update_own" on public.profiles for update
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "profiles_delete_own" on public.profiles for delete
using ((select auth.uid()) = user_id);

create policy "custom_foods_select_own" on public.custom_foods for select
using ((select auth.uid()) = user_id);
create policy "custom_foods_insert_own" on public.custom_foods for insert
with check ((select auth.uid()) = user_id);
create policy "custom_foods_update_own" on public.custom_foods for update
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "custom_foods_delete_own" on public.custom_foods for delete
using ((select auth.uid()) = user_id);

create policy "meal_logs_select_own" on public.meal_logs for select
using ((select auth.uid()) = user_id);
create policy "meal_logs_insert_own" on public.meal_logs for insert
with check ((select auth.uid()) = user_id);
create policy "meal_logs_update_own" on public.meal_logs for update
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "meal_logs_delete_own" on public.meal_logs for delete
using ((select auth.uid()) = user_id);
