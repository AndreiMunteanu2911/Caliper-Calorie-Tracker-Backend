# Caliper Backend

This is the service that powers Caliper behind the scenes. The app that users
see is in `Caliper-Frontend`; this backend stores and protects nutrition data,
looks up foods, calculates totals, and talks to AI services.

In plain terms: the frontend is the interface, and this backend is the engine.

## What The Backend Does For Users

Caliper depends on the backend for the core nutrition experience:

- Keeps each user's meal logs private and separate.
- Calculates daily calories and macros from logged foods.
- Groups logs by local date and timezone.
- Searches foods through USDA FoodData Central.
- Looks up packaged foods by barcode through Open Food Facts.
- Saves custom foods.
- Analyzes meal photos with AI.
- Runs the AI nutrition advisor and saves conversation history.
- Tracks weight entries over time.
- Calculates calorie and macro targets with a TDEE calculator.
- Returns helpful error messages when an external service is unavailable.

Most users never interact with this project directly, but they rely on it every
time they log food, scan a barcode, open the dashboard, or ask the advisor a
question.

## Main Features

### Accounts And Privacy

Users sign in through Supabase. The frontend sends the user's Supabase token to
this backend, and the backend checks that token before allowing access to any
private data.

Database policies also protect user data so one user cannot read another user's
logs, profile, advisor messages, custom foods, or weight entries.

### Dashboard Totals

The backend aggregates the foods a user logged for a day and returns:

- calories eaten
- calories remaining
- protein, carbs, and fat eaten
- macro targets
- editable meal-log rows

Dates are calculated using the user's timezone, so "today" matches the user's
actual day.

### Food Lookup

The backend can:

- Search USDA foods by text.
- Find packaged foods by barcode.
- Normalize nutrition values so the app can calculate nutrients for any amount
  in grams.

### Meal Photo Analysis

When a user uploads or captures a meal photo, the backend sends the image to
OpenRouter and asks for structured food estimates. The response is checked
before it is sent back to the app.

### AI Nutrition Advisor

The advisor uses context from the user's own data:

- today's logged foods
- today's remaining macros
- recent calorie and macro history
- previous messages in the current conversation

Conversation history is saved so the user can come back to older chats.

### Weight And Goals

The backend stores dated weight entries and calculates TDEE-based calorie and
macro targets from profile details such as age, height, weight, activity level,
and goal.

## For People Setting It Up

You need accounts/API keys for:

- Supabase, for accounts and the database
- USDA FoodData Central, for food search
- OpenRouter, for AI meal analysis and advisor chat

### Requirements

- Python 3.13
- A Supabase project
- PostgreSQL connection credentials from Supabase
- USDA FoodData Central API key
- OpenRouter API key

## Run Locally

Create a virtual environment:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a local environment file:

```powershell
Copy-Item .env.example .env.local
```

Fill in `.env.local`:

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

Start the API:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Useful local URLs:

- API docs: `http://localhost:8000/docs`
- Machine-readable API schema: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/health`

The backend loads `.env.local` and `.env` automatically during local
development. Environment variables already set by the operating system or Vercel
take priority.

## Database Setup

The database migrations live in:

```text
supabase/migrations/
```

They create the tables, indexes, helper functions, triggers, and Row Level
Security rules for:

- profiles
- custom foods
- meal logs
- advisor conversations
- advisor messages
- weight logs

Apply them with the Supabase CLI:

```powershell
supabase link --project-ref your-project-ref
supabase db push
```

The migrations assume a Caliper database schema. Review them carefully before
applying them to an existing production database.

## Environment Variables Explained

- `DATABASE_URL`: PostgreSQL connection string used by the backend.
- `SUPABASE_URL`: Supabase project URL, also used for modern JWT verification.
- `SUPABASE_JWT_SECRET`: JWT secret for older HS256 Supabase projects. Leave
  blank if your project uses JWKS/asymmetric signing.
- `USDA_API_KEY`: enables food search.
- `OPENROUTER_API_KEY`: enables meal photo analysis and advisor chat.
- `OPENROUTER_APP_URL`: optional OpenRouter attribution URL.
- `OPENROUTER_APP_NAME`: optional OpenRouter attribution name.
- `CORS_ORIGINS`: web origins allowed to call the backend from a browser.
- `CORS_ORIGIN_REGEX`: development-friendly origin pattern.

Native iOS and Android requests are not limited by browser CORS rules, but Expo
Web is.

Never expose database passwords, OpenRouter keys, USDA keys, or Supabase
service-role keys in the frontend.

## API Overview

All `/api/v1` routes require a valid Supabase bearer token unless noted
otherwise.

### Dashboard

```http
GET /api/v1/dashboard?timezone=Europe/Bucharest
```

Returns today's nutrition totals and editable meal logs for the signed-in user.

### Meal Logs

```http
POST   /api/v1/meal-logs
PATCH  /api/v1/meal-logs/{log_id}
DELETE /api/v1/meal-logs/{log_id}
```

Meal logs store the original food nutrition values and the amount eaten. If a
user changes the amount later, nutrients are recalculated from the original
per-100 g values.

### Food Search And Barcode Lookup

```http
GET /api/v1/food/search?query=chicken
GET /api/v1/food/barcode/3017620422003
```

Search uses USDA FoodData Central. Barcode lookup uses Open Food Facts.

### AI Meal Analysis

```http
POST /api/v1/ai/analyze-plate
```

Accepts image data and returns estimated foods, calories, protein, carbs, fats,
and a confidence explanation.

### AI Advisor

```http
GET  /api/v1/ai/conversations
GET  /api/v1/ai/chat
POST /api/v1/ai/chat
```

The backend owns advisor history and sends relevant nutrition context to the AI
model. User and assistant messages are saved together after a successful
response.

### Weight Logs

```http
GET    /api/v1/weight-logs
POST   /api/v1/weight-logs
DELETE /api/v1/weight-logs/{log_id}
```

Saving a new entry for a date that already has one updates that date's weight.

### TDEE Calculator

```http
POST /api/v1/profile/tdee
```

Uses the Mifflin-St Jeor equation, an activity multiplier, and the selected goal
to estimate calorie and macro targets.

## Error Responses

Errors use a consistent shape:

```json
{
  "error": {
    "code": "external_service_unavailable",
    "message": "USDA FoodData Central: Food search is temporarily unavailable."
  }
}
```

The backend handles common cases such as invalid input, missing resources,
authentication problems, invalid timezones, external API failures, malformed
external API responses, and unexpected internal failures.

Unexpected technical details are logged on the server but are not shown to the
user.

## How The Code Is Organized

```text
app/
  core/
    config.py          Reads settings from environment variables
    database.py        Database connection management
    errors.py          Shared error types
    security.py        Supabase token verification
  routers/             API route definitions
  schemas/             Request and response shapes
  services/            Food, meal, AI, profile, and weight logic

supabase/
  migrations/          Database schema and security rules

main.py                FastAPI application entry point
```

Routers focus on HTTP requests and responses. Services contain most of the
business logic, database work, external API calls, and AI payload handling.

## Main Technologies

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

## Deploying To Vercel

The backend and frontend should be deployed as separate Vercel projects. Deploy
the backend first, then point the frontend to this backend's production URL.

### 1. Prepare Supabase

Apply the database migrations and collect:

- Supabase project URL
- PostgreSQL connection string
- Supabase JWT secret, if your project uses HS256 signing

For serverless deployments, use the Supabase transaction pooler connection
string. If needed, add `?sslmode=require`.

### 2. Create The Backend Project

Import this repository into Vercel and configure:

- Root Directory: repository root
- Framework Preset: FastAPI if detected, otherwise Other
- Python version: 3.13 where available

`vercel.json` routes requests to `main.py`.

### 3. Set Production Environment Variables

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

Do not give untrusted preview deployments production database credentials.

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

Set the frontend environment variable:

```env
EXPO_PUBLIC_API_URL=https://your-backend.vercel.app/api/v1
```

Also set backend `CORS_ORIGINS` to the exact frontend origin.

## Operational Notes

- External provider failures return typed errors instead of raw provider
  exceptions.
- Daily aggregation uses the timezone supplied by the app.
- The database pool is created lazily, so `/health` can start even before the
  first database-backed request.
- CORS should be restricted to known production frontend origins.
- `openrouter/free` chooses a currently available free model through
  OpenRouter; exact model availability can change.
