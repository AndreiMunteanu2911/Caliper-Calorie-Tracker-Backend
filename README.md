# Caliper Backend

FastAPI service for Caliper authentication, food lookup, meal logging, macro
aggregation, AI meal analysis, and diet advisor chat.

## Features

- Supabase JWT authentication
- Async PostgreSQL connection pooling
- Timezone-aware daily macro aggregation
- User-scoped meal-log CRUD
- Open Food Facts barcode lookup
- USDA FoodData Central text search
- OpenRouter free-router vision analysis
- Context-aware nutrition advisor chat
- Weight logging with user-scoped history
- TDEE and automatic calorie/macro goal calculation
- Strict Pydantic validation
- Typed global error responses
- Supabase schema and Row Level Security migration

## Technology

- Python 3.13
- FastAPI
- Uvicorn
- Pydantic 2
- asyncpg
- httpx
- PyJWT
- Supabase PostgreSQL and Auth
- Open Food Facts
- USDA FoodData Central
- OpenRouter

## Architecture

```text
app/
  core/
    config.py          Environment-backed settings
    database.py        FastAPI database dependency
    errors.py          Typed application errors
    security.py        Supabase JWT verification
  routers/             HTTP binding and service delegation
  schemas/             Strict Pydantic request/response models
  services/            Business logic and external integrations

supabase/
  migrations/
    001_init.sql       Tables, functions, triggers, indexes, and RLS
    002_advisor_conversations.sql  Persistent advisor history and RLS
    004_weight_logs.sql  Weight history, indexes, triggers, and RLS

main.py                FastAPI application and global error handlers
```

Routers contain HTTP concerns only. Database operations, external API calls,
normalization, aggregation, and AI payload handling live in service modules.

## Requirements

- Python 3.13
- A Supabase project
- PostgreSQL connection credentials
- USDA FoodData Central API key
- OpenRouter API key

## Installation

Create and activate a virtual environment:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Environment

Create an uncommitted `.env.local` from `.env.example`:

```powershell
Copy-Item .env.example .env.local
```

Configure:

```env
DATABASE_URL=postgresql://postgres:password@db.example.supabase.co:5432/postgres
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=
USDA_API_KEY=your-usda-key
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_APP_URL=
OPENROUTER_APP_NAME=
CORS_ORIGINS=http://localhost:8081,http://localhost:19006
CORS_ORIGIN_REGEX=^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$
```

### Required Variables

- `DATABASE_URL`: direct PostgreSQL connection used by `asyncpg`
- `SUPABASE_URL`: used to obtain Supabase JWKS when asymmetric JWT signing is enabled
- `USDA_API_KEY`: USDA FoodData Central access
- `OPENROUTER_API_KEY`: meal analysis and advisor chat

### Supabase JWT Verification

The backend supports:

- `SUPABASE_JWT_SECRET` for legacy HS256 projects
- `SUPABASE_URL` JWKS discovery for asymmetric RS256/ES256 projects

The backend reads the token algorithm and selects HS256 secret verification or
asymmetric JWKS verification accordingly.

### Optional OpenRouter Attribution

`OPENROUTER_APP_URL` and `OPENROUTER_APP_NAME` only set the optional
`HTTP-Referer` and `X-Title` OpenRouter headers. They are not required for API
access and may remain empty.

### CORS

`CORS_ORIGINS` is a comma-separated allowlist. Add production web origins and
any Expo Web development origins that need browser access.

`CORS_ORIGIN_REGEX` defaults to localhost and `127.0.0.1` on any port so Expo
Web remains usable if its development port changes.

Native iOS and Android requests are not governed by browser CORS enforcement.

## Database Setup

The migrations are located at:

```text
supabase/migrations/001_init.sql
supabase/migrations/002_advisor_conversations.sql
supabase/migrations/004_weight_logs.sql
```

They create:

- `profiles`
- `custom_foods`
- `meal_logs`
- `advisor_conversations`
- `advisor_messages`
- `weight_logs`
- profile creation and timestamp triggers
- daily macro aggregation function
- indexes for user/date and food-name access
- SELECT, INSERT, UPDATE, and DELETE RLS policies

Apply it with the Supabase CLI from this repository:

```powershell
supabase link --project-ref your-project-ref
supabase db push
```

The migration assumes a new database schema. Review existing production schemas
before applying it to an established project.

## Development

The backend loads `.env.local` and `.env` automatically for local development.
Existing process variables take precedence, so Vercel-injected values are not
overwritten.

Run:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API documentation:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/health`

## API

All `/api/v1` routes require a valid Supabase bearer token.

### Dashboard

```http
GET /api/v1/dashboard?timezone=Europe/Bucharest
```

Returns server-aggregated daily macro progress and the authenticated user's
editable meal-log rows for that local date.

### Meal Logs

```http
POST /api/v1/meal-logs
PATCH /api/v1/meal-logs/{log_id}
DELETE /api/v1/meal-logs/{log_id}
```

Create payload:

```json
{
  "food": {
    "external_id": "171077",
    "source": "usda",
    "name": "Chicken breast, roasted",
    "brand": null,
    "serving_size_g": 100,
    "calories": 165,
    "protein": 31,
    "carbs": 0,
    "fats": 3.6
  },
  "meal_type": "lunch",
  "quantity_g": 180
}
```

The service stores immutable per-100 g nutrient values and calculates the
consumed nutrient snapshot. Weight edits are recalculated from the original
per-100 g values to avoid cumulative rounding drift.

### Barcode Lookup

```http
GET /api/v1/food/barcode/3017620422003
```

Normalizes Open Food Facts nutrition values per 100 g.

### Food Search

```http
GET /api/v1/food/search?query=chicken
```

Searches USDA Foundation and SR Legacy foods and normalizes calories, protein,
carbohydrates, and fats per 100 g.

### Plate Analysis

```http
POST /api/v1/ai/analyze-plate
```

Accepts base64 image data, media type, and optional meal context. OpenRouter is
called with:

```json
{
  "model": "openrouter/free"
}
```

The parser handles plain JSON, fenced JSON markdown, and surrounding model text,
then validates the extracted object against the strict Pydantic response model.

### Diet Advisor

```http
GET  /api/v1/ai/chat
POST /api/v1/ai/chat
```

The backend owns and persists advisor history. It loads up to 20 recent messages
for model context and returns up to 200 recent messages to the client.

Each advisor request includes live remaining macros, every food logged today,
30 calendar days of aggregate calorie and macro averages, and the number of days
that contain food logs. Missing days are treated as incomplete data rather than
confirmed zero intake. User and assistant messages are committed together after
OpenRouter returns successfully.

### Weight History

```http
GET    /api/v1/weight-logs
POST   /api/v1/weight-logs
DELETE /api/v1/weight-logs/{log_id}
```

Saving another entry for the same date updates that date's weight.

### TDEE Calculator

```http
POST /api/v1/profile/tdee
```

Uses the Mifflin-St Jeor equation, an activity multiplier, and the selected
lose, maintain, or gain goal. The response includes calorie and macro targets
that can be applied to the user's profile.

## Error Format

Errors use a consistent envelope:

```json
{
  "error": {
    "code": "external_service_unavailable",
    "message": "USDA FoodData Central: Food search is temporarily unavailable."
  }
}
```

Handled categories include:

- request validation errors
- authentication and HTTP errors
- missing resources
- invalid timezones
- external API failures
- malformed external API payloads
- unexpected internal failures

Unexpected exception details are logged server-side and are not exposed to the
client.

## Authentication And Authorization

The mobile client sends its Supabase access token:

```http
Authorization: Bearer <supabase-access-token>
```

FastAPI verifies the token and uses its `sub` claim as the user ID. Meal-log
queries also include that user ID directly, while Supabase RLS protects direct
database access through Supabase clients.

Never expose the Supabase service-role key to the frontend.

## Deployment

## Deploying FastAPI To Vercel

The backend and frontend must be deployed as separate Vercel projects. Deploy
this backend first.

### 1. Prepare Supabase

Apply the database migration and obtain:

- Supabase project URL
- PostgreSQL pooler connection string
- Supabase JWT secret for HS256 projects, or use project JWKS through
  `SUPABASE_URL`

For serverless deployments, use the Supabase transaction pooler connection
string. If Supabase does not include it automatically, append
`?sslmode=require`.
The API disables asyncpg's prepared-statement cache for transaction-pooler
compatibility.

### 2. Create The Backend Project

Import this repository into Vercel and configure:

- Root Directory: repository root
- Framework Preset: FastAPI, if detected; otherwise Other
- Python version: 3.13 where available

`vercel.json` routes all requests to `main.py`.

### 3. Configure Vercel Variables

In Vercel Project Settings, add the following for Production:

```env
DATABASE_URL=postgresql://...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_JWT_SECRET=
USDA_API_KEY=your-usda-key
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_APP_URL=https://your-frontend.vercel.app
OPENROUTER_APP_NAME=Caliper
CORS_ORIGINS=https://your-frontend.vercel.app
```

`OPENROUTER_APP_URL` and `OPENROUTER_APP_NAME` remain optional. The other
provider and database values are required for their respective features.

Configure Preview separately. Do not give untrusted preview branches production
database credentials.

### 4. Deploy

Push to the production branch or run:

```powershell
npx vercel --prod
```

Verify:

```text
https://your-backend.vercel.app/health
https://your-backend.vercel.app/docs
```

### 5. Connect The Frontend

Set the frontend Vercel project's production variable:

```env
EXPO_PUBLIC_API_URL=https://your-backend.vercel.app/api/v1
```

Set backend CORS to the exact frontend origin and redeploy both projects after
changing environment values.

### Environment Strategy

Use:

- `.env.local`: uncommitted local secrets and localhost configuration
- Vercel Development variables: values pulled by `vercel env pull`
- Vercel Preview variables: staging or restricted preview services
- Vercel Production variables: production secrets and URLs
- `.env.example`: committed variable-name documentation

Do not commit `.env.production` containing secrets. Vercel environment scoping
is the authoritative production configuration.

The application creates its asyncpg pool lazily on the first database-backed
request. This allows `/health` to start independently and avoids crashing a
Vercel function during module initialization.

## Operational Notes

- `openrouter/free` selects a free model dynamically. Vision capability and
  availability depend on the models currently exposed by OpenRouter.
- External API failures return typed `503` responses rather than raw provider
  exceptions.
- Daily aggregation uses the supplied IANA timezone and PostgreSQL date
  conversion.
- CORS should be restricted to known production web origins.
