# CareBank - AI-Powered Financial Wellness System

CareBank is a full-stack financial wellness demo with Supabase-backed auth and data storage, a FastAPI backend, and a React dashboard for analysis, AI chat, CSV transaction ingestion, and manual transaction entry.

## Stack

- Backend: Python, FastAPI, httpx, python-multipart
- Frontend: React (Vite), Tailwind CSS, Recharts
- Auth and data: Supabase Auth + PostgREST + Row Level Security
- AI: OpenRouter or OpenAI-compatible API with a deterministic fallback mode

## Features

- Email/password sign up and sign in against Supabase Auth
- Backend-protected `GET /analyze` and `POST /chat` routes that verify Supabase bearer tokens
- Deterministic financial scoring engine with explainable component breakdowns
- Deterministic simulation engine for projected balance and spend-safety decisions
- AI explanation layer on top of simulation output using only structured projection fields
- Lightweight anomaly detection to flag suspicious transactions based on user behavior
- User-scoped transaction reads, manual transaction entry, and CSV imports into the `transactions` table
- Dashboard, analytics, recommendations, and AI assistant backed by each user's own data

## Backend setup

Create `carebank-backend/.env` from the example below:

```env
APP_ENV=development
REQUIRE_STRICT_SECURITY=false
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
INTERNAL_METRICS_TOKEN=your_internal_metrics_token
FRONTEND_URL=http://localhost:5173
OPENROUTER_API_KEY=
AI_CATEGORIZATION_ENABLED=false
LLM_PROVIDER=openrouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
APP_URL=http://localhost:5173
ENABLE_AUDIT_PERSISTENCE=false
ENABLE_LOCAL_EVENT_FALLBACK=false
ENABLE_SAMPLE_DATA_FALLBACK=false
ENABLE_WEBSOCKET_DEV_FALLBACK=false
RATE_LIMIT_ENABLED=false
```

Run the backend:

```bash
cd carebank-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.
The health endpoint is available at `http://localhost:8000/health`.

If Supabase is temporarily unavailable during local development, you can set `ENABLE_SAMPLE_DATA_FALLBACK=true` to let authenticated demo requests use `carebank-backend/data/transactions.json` for read-only analysis endpoints.

## Frontend setup

Create `carebank-frontend/.env` from the example below:

```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

Run the frontend:

```bash
cd carebank-frontend
npm install
npm run dev
```

The app will run at `http://localhost:5173`.

## Preferences and recovery

- Notification preferences are persisted through the backend at `GET /preferences` and `PUT /preferences`
- Password reset requests can be initiated from the sign-in screen through Supabase Auth
- When `ENABLE_SAMPLE_DATA_FALLBACK=true`, transaction-powered routes can fall back to sample data during Supabase `5xx` outages

## Verification

Backend tests:

```bash
cd carebank-backend
python -m unittest discover -s tests -v
```

Frontend build check:

```bash
cd carebank-frontend
npm run check
```

## Supabase schema

Create the following tables and policies in Supabase:

```sql
create table profiles (
  id uuid primary key,
  email text,
  created_at timestamp default now()
);

create table transactions (
  id uuid default gen_random_uuid() primary key,
  user_id uuid,
  amount numeric,
  category text,
  description text,
  created_at timestamp default now(),
  fraud_risk text,
  fraud_flags jsonb
);

alter table profiles enable row level security;
alter table transactions enable row level security;

create policy "Users can access their profile"
on profiles
for all
using (auth.uid() = id)
with check (auth.uid() = id);

create policy "Users can access their transactions"
on transactions
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);
```

## CSV ingestion format

The upload endpoint accepts authenticated `multipart/form-data` CSV uploads and looks for:

- Date: `date`, `created_at`, `transaction_date`, or `posted_at`
- Amount: `amount`, `value`, `amt`, `debit`, or `credit`
- Description: `description`, `details`, `narration`, or `merchant`
- Category: `category` or `type` (optional, inferred when missing)

## Manual transaction entry

- The Settings page also supports adding one transaction at a time without a CSV file
- Manual transactions are validated, fraud-checked, and inserted into the same `transactions` table as CSV imports
- Required fields: `date`, `description`, `amount`, and `category`

## Protected API routes

- `GET /analyze`
- `GET /fraud-check`
- `GET /financial-score`
- `POST /chat`
- `POST /simulate`
- `POST /transactions/manual`
- `POST /transactions/upload-csv`
- `POST /realtime/ws-ticket`
