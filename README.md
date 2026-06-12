# Caliper Backend

FastAPI service for Caliper authentication, food lookup, meal logging, macro
aggregation, AI plate analysis, and diet advisor chat.

## Features

- Supabase JWT authentication
- Async PostgreSQL connection pooling
- Timezone-aware daily macro aggregation
- User-scoped meal-log CRUD
- Open Food Facts barcode lookup
- USDA FoodData Central text search
- OpenRouter free-router vision analysis
- Context-aware nutrition advisor chat
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

Create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
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
```

### Required Variables

- `DATABASE_URL`: direct PostgreSQL connection used by `asyncpg`
- `SUPABASE_URL`: used to obtain Supabase JWKS when asymmetric JWT signing is enabled
- `USDA_API_KEY`: USDA FoodData Central access
- `OPENROUTER_API_KEY`: plate analysis and advisor chat

### Supabase JWT Verification

The backend supports:

- `SUPABASE_JWT_SECRET` for legacy HS256 projects
- `SUPABASE_URL` JWKS discovery for asymmetric RS256/ES256 projects

When both are provided, `SUPABASE_JWT_SECRET` is used.

### Optional OpenRouter Attribution

`OPENROUTER_APP_URL` and `OPENROUTER_APP_NAME` only set the optional
`HTTP-Referer` and `X-Title` OpenRouter headers. They are not required for API
access and may remain empty.

### CORS

`CORS_ORIGINS` is a comma-separated allowlist. Add production web origins and
any Expo Web development origins that need browser access.

Native iOS and Android requests are not governed by browser CORS enforcement.

## Database Setup

The migration is located at:

```text
supabase/migrations/001_init.sql
```

It creates:

- `profiles`
- `custom_foods`
- `meal_logs`
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

Load `.env` into the process using your preferred environment manager, then run:

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
POST /api/v1/ai/chat
```

The backend calculates live daily macro progress and injects remaining calories,
protein, carbohydrates, and fats into the advisor system prompt. Up to 20 prior
conversation messages may be supplied for context.

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

`vercel.json` contains a Vercel Python deployment configuration. Configure all
environment variables in the deployment environment.

The application uses a persistent asyncpg connection pool during the FastAPI
lifespan. Confirm the chosen serverless platform and Supabase connection mode
support the expected concurrency and connection limits. Supabase's pooler is
recommended for serverless deployment.

## Operational Notes

- `openrouter/free` selects a free model dynamically. Vision capability and
  availability depend on the models currently exposed by OpenRouter.
- External API failures return typed `503` responses rather than raw provider
  exceptions.
- Daily aggregation uses the supplied IANA timezone and PostgreSQL date
  conversion.
- CORS should be restricted to known production web origins.

