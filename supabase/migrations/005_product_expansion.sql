alter table public.profiles
  add column onboarding_status text,
  add column sex text,
  add column age integer,
  add column height_cm numeric(6, 2),
  add column activity_level text,
  add column goal text,
  add column target_weight_kg numeric(6, 2);

update public.profiles set onboarding_status = 'completed';

alter table public.profiles
  alter column onboarding_status set default 'pending',
  alter column onboarding_status set not null,
  add constraint profiles_onboarding_status_check
    check (onboarding_status in ('pending', 'completed', 'skipped')),
  add constraint profiles_sex_check
    check (sex is null or sex in ('female', 'male')),
  add constraint profiles_age_check
    check (age is null or age between 14 and 100),
  add constraint profiles_height_check
    check (height_cm is null or height_cm between 120 and 250),
  add constraint profiles_activity_level_check
    check (
      activity_level is null or activity_level in (
        'sedentary', 'light', 'moderate', 'very_active', 'extra_active'
      )
    ),
  add constraint profiles_goal_check
    check (goal is null or goal in ('lose', 'maintain', 'gain')),
  add constraint profiles_target_weight_check
    check (target_weight_kg is null or target_weight_kg between 20 and 500);

alter table public.custom_foods
  add column fiber numeric(8, 2) not null default 0 check (fiber >= 0),
  add column sugar numeric(8, 2) not null default 0 check (sugar >= 0),
  add column sodium_mg numeric(10, 2) not null default 0 check (sodium_mg >= 0),
  add column saturated_fat numeric(8, 2) not null default 0 check (saturated_fat >= 0),
  add column is_favorite boolean not null default false,
  add column last_used_at timestamptz;

alter table public.meal_logs
  add column external_id text not null default '',
  add column source text not null default 'unknown',
  add column fiber_per_100g numeric(8, 2) not null default 0 check (fiber_per_100g >= 0),
  add column sugar_per_100g numeric(8, 2) not null default 0 check (sugar_per_100g >= 0),
  add column sodium_mg_per_100g numeric(10, 2) not null default 0 check (sodium_mg_per_100g >= 0),
  add column saturated_fat_per_100g numeric(8, 2) not null default 0 check (saturated_fat_per_100g >= 0),
  add column fiber numeric(8, 2) not null default 0 check (fiber >= 0),
  add column sugar numeric(8, 2) not null default 0 check (sugar >= 0),
  add column sodium_mg numeric(10, 2) not null default 0 check (sodium_mg >= 0),
  add column saturated_fat numeric(8, 2) not null default 0 check (saturated_fat >= 0);
