# Testing and QA Guide

## Backend

Run regression suite:

```bash
cd carebank-backend
python -m unittest discover -s tests -v
```

Run coverage:

```bash
cd carebank-backend
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
```

## Frontend

Build check:

```bash
cd carebank-frontend
npm run build
```

Run unit tests:

```bash
cd carebank-frontend
npm run test:run
```

## CI Overview

The GitHub Actions pipeline runs:

- Backend tests with coverage
- Optional backend lint checks (`ruff`, `black --check`)
- Frontend build
- Frontend Vitest test suite
- Static migration validation tests
- Optional dependency security scans (`pip-audit`, `npm audit`)

## Safe CI Environment Defaults

CI uses non-secret placeholder values and does not require live Supabase, Redis, or OpenRouter credentials.

Recommended placeholders:

- `APP_ENV=development`
- `ENABLE_SAMPLE_DATA_FALLBACK=false`
- `AI_CATEGORIZATION_ENABLED=false`
- `SUPABASE_URL=https://example.supabase.co`
- `SUPABASE_ANON_KEY=test-anon-key`
- `SUPABASE_SERVICE_ROLE_KEY=test-service-role`
- `OPENROUTER_API_KEY=`

## Manual smoke checklist

If you are validating the workspace locally without end-to-end tooling, the minimum smoke flow is:

1. Sign in successfully.
2. Upload a transaction CSV.
3. Confirm the dashboard loads and shows score, risk, behavior, guidance, and alerts modules.
4. Open the floating chat/copilot and send a question.
5. Open the history workspace and verify each tab loads without a crash.
6. Confirm the realtime alert center opens and shows connection state without exposing raw payloads.
