# CrickOps AI

CrickOps AI is a global cricket tournament operations copilot for amateur, academy, university,
club, corporate, community, and regional organizers. Version 1 plans a fixed eight-team event,
compares three solver-validated schedules, and repairs rain or venue disruption with minimum change.

- App: <https://crickops.vercel.app>
- API health: <https://crickops-api-production.up.railway.app/health/ready>
- Product: [`scope.md`](scope.md) · Requirements: [`prd.md`](prd.md) · Design: [`spec.md`](spec.md)

## Hero flow

Load a sample, review structured constraints, generate Balanced/Weather-first/Fairness-first
options, approve one official workspace schedule, trigger deterministic rain, compare the repair,
approve it, and inspect the versioned audit timeline. T10 uses a 120-minute operational allocation;
T20 uses 240 minutes and is the hero preset. Allocations are planning blocks, not duration promises.

## Architecture

- Next.js 15/React 19 on Vercel with a same-origin `/api/*` Railway proxy.
- FastAPI API plus retention worker in non-root Docker containers on Railway.
- Railway PostgreSQL for durable guest state and lifecycle data.
- OR-Tools CP-SAT for deterministic generation, repair, scoring, and validation.
- GPT-5.6 through the OpenAI Agents SDK for the primary six-role workflow.
- Configurable model fallback and a fully functional deterministic degraded mode.
- Coordinate-based Open-Meteo guidance plus reproducible deterministic weather.

## Local setup

Requires Node.js 20+, pnpm 10.13.1, Python 3.12, and uv.

```powershell
pnpm install --frozen-lockfile
uv sync --locked
Copy-Item .env.example .env
uv run uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
pnpm --filter @crickops/web dev
```

Never commit provider keys or production secrets. Local mode remains deterministic unless live
services are deliberately configured. Judges need no installation, registration, or API key.

## Verification

```powershell
pnpm install --frozen-lockfile
uv sync --locked
pnpm lint
pnpm test
uv run ruff check .
uv run pytest
$env:CRICKOPS_E2E_BASE_URL="https://crickops.vercel.app"
pnpm --filter @crickops/web test:e2e
```

Railway uses [`Dockerfile`](Dockerfile) and [`railway.toml`](railway.toml). The pre-deploy command
applies the schema; the same image runs `crickops-api` and `crickops-worker`. Liveness is
`/health/live`; readiness is `/health/ready`. See the
[`judging runbook`](docs/demo/judging-availability-runbook.md) and
[`deployment evidence`](docs/evidence/deployment-gate.md).

## Privacy and limits

Guest workspaces expire after a seven-day sliding inactivity period. Do not enter personal,
confidential, financial, or payment information. Version 1 has no authentication, collaboration,
scoring, standings, DLS, external publishing, stakeholder messaging, worldwide ground discovery,
or official weather/safety decisions. Full boundaries are in `scope.md`.

Codex contributions and human decisions are recorded in
[`docs/decisions/codex-collaboration.md`](docs/decisions/codex-collaboration.md).

