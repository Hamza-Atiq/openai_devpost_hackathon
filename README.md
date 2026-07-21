# CrickOps AI

CrickOps AI is a global cricket tournament operations copilot for amateur, academy, university,
club, corporate, community, and regional organizers. Version 1 plans a fixed eight-team event,
compares three solver-validated scheduling profiles, and repairs rain or venue disruptions with
minimum change.

- Live app: <https://crickops.vercel.app>
- API health: <https://crickops-api-production.up.railway.app/health/ready>
- Codex `/feedback` IDs: `019f7d52-53db-7641-b7fe-b5cc723de468`, `019f652a-dec1-7c71-aa20-1559804a3721`
- Codex `/status` session IDs: `019f652a-dec1-7c71-aa20-1559804a3721`, `019f7d52-53db-7641-b7fe-b5cc723de468`
- Category: **Work and Productivity**
- Product: [`scope.md`](scope.md) · Requirements: [`prd.md`](prd.md) · Design: [`spec.md`](spec.md)

The repository was created during the OpenAI Build Week submission period. Its first commit is
dated July 16, 2026; no part of this project existed before the hackathon.

## Judge quickstart

No installation, registration, API key, or payment is required. Open the
[live app](https://crickops.vercel.app) and:

1. Choose **Global Community Cricket Cup** and press **Load sample**.
2. Review the setup, tick the hard-constraint confirmation, and press
   **Confirm and generate schedules**.
3. Compare Balanced, Weather-first, and Fairness-first, then review and approve one option.
4. Open **Recovery**, declare a rain disruption on a fixture, and generate a repaired draft.
5. Review and approve the repair, then open **Activity** for the versioned audit timeline.

The complete path takes about three minutes. **Build your own tournament** starts from an editable
eight-team, two-group, two-venue skeleton. Guest workspaces are isolated per browser and expire
after seven days of inactivity.

The three profiles are generated and validated independently, but two profiles can legitimately
converge on the same fixture placement. When that happens, the comparison displays a
**Same fixture placement** disclosure rather than pretending the schedules are different.

## Hero flow

Load a sample, review structured constraints, generate Balanced, Weather-first, and Fairness-first
profiles, approve one official workspace schedule, declare a disruption, compare the
minimum-change repair, approve it, and inspect the audit timeline. T10 uses a 120-minute
operational allocation; T20 uses 240 minutes and is the hero preset. These are planning blocks,
not promises about match duration.

## Architecture

- Next.js 15 and React 19 on Vercel, with a same-origin `/api/*` Railway proxy.
- FastAPI API and retention worker in non-root Docker containers on Railway.
- Railway PostgreSQL for durable guest state and lifecycle data.
- OR-Tools CP-SAT for deterministic schedule generation and repair.
- Independent deterministic validation before any schedule can be approved.
- GPT-5.6 through the OpenAI Agents SDK for the Tournament Director and five specialist roles.
- Configurable model fallback and a fully functional deterministic degraded mode.
- Coordinate-based Open-Meteo guidance plus reproducible deterministic weather data.

## Building with Codex and GPT-5.6

Two different things carry the name “AI” in this project, and keeping them separate was the
central engineering decision: **Codex built the software; GPT-5.6 runs inside the software.**
Neither is allowed to decide or approve a fixture.

### How I worked with Codex

I did not prompt Codex feature by feature. I wrote four authoritative documents:

1. [`scope.md`](scope.md) — what Version 1 deliberately refuses to do.
2. [`prd.md`](prd.md) — testable product requirements.
3. [`spec.md`](spec.md) — the technical design and safety boundaries.
4. [`checklist.md`](checklist.md) — TASK-001 through TASK-064.

I then worked through the checklist in order and test-first. Every task names the requirement IDs
it satisfies, giving Codex a verifiable definition of done instead of an open-ended prompt. The
specification documents, tests, commit history, and pull requests preserve that development trail.

### Where Codex accelerated the work

- **CP-SAT modelling:** translating eight teams, two groups, fifteen fixtures, local-day limits,
  venue exclusivity, and stage chronology into a deterministic model plus an independent validator.
- **Deployment engineering:** Railway portability, non-root containers, schema migrations,
  fail-closed configuration, health checks, and a retention worker.
- **Strict agent schemas:** forcing agent output through typed structures so a model cannot emit a
  free-text fixture mutation.
- **Guest-state durability:** PostgreSQL-backed workspace restoration so a judge can reload without
  losing the tournament.
- **Adversarial QA:** reproducing production defects with focused tests and repairing them across the
  API and web application. Examples include the blank-tournament dead end, decimal coordinate
  editing, stale Options navigation, provider-error degradation, venue-timezone display, and
  structured specialist evidence in the audit timeline.
- **Profile semantics:** selecting Weather-first and Fairness-first representatives from independently
  validated candidates using their authoritative weather and fairness metrics, instead of presenting
  a profile whose displayed metric contradicts its name.

### Where I made the decisions

- The fixed Version 1 competition shape and the choice to ship a narrow, reliable workflow.
- Weather is **planning guidance, never an official safety decision**. The organizer owns every
  delay, move, and cancellation.
- Three comparable optimization profiles are more useful than one unexplained “best” answer.
- Official schedules are immutable versions. Repairs create drafts and never silently edit an
  approved schedule.
- The six agent roles exist only where a role has a specific evidence contract—no agent theatre.
- Human confirmation is required for hard constraints and every schedule approval.

### How GPT-5.6 works inside the product

GPT-5.6 runs the Tournament Director and five specialist roles through the OpenAI Agents SDK. It
interprets organizer intent, explains validated profile trade-offs, and narrates recovery evidence.

It is deliberately fenced in:

- It reads validated solver and workspace evidence; it does not create schedules or metrics.
- It refuses to invent unsupported facts.
- It cannot approve a schedule or bypass independent validation.
- Material turns record provider, model, mode, validation status, and specialist evidence in the
  workspace audit timeline.
- If the provider fails, the application reports degraded mode while deterministic setup,
  scheduling, validation, repair, and approval controls remain available.

The agent provenance recorded by live GPT-backed turns identifies provider `openai`, model
`gpt-5.6`, and validation status `valid`.

### Evidence

The commit history is authoritative. Codex contributions and human decisions are summarized in
[`docs/decisions/codex-collaboration.md`](docs/decisions/codex-collaboration.md), with deployment
and quality evidence under [`docs/evidence`](docs/evidence).

## Local setup

Requires Node.js 20+, pnpm 10.13.1, Python 3.12, and uv.

```powershell
pnpm install --frozen-lockfile
uv sync --locked
Copy-Item .env.example .env
```

Start the API in one terminal:

```powershell
uv run uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

Start the web application in a second terminal:

```powershell
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

Latest consolidated gate: **347 backend tests passed, 1 skipped; 65 frontend tests passed;** the
Next.js production build, ESLint, Ruff, OpenAPI snapshot, and diff checks also passed.

Railway uses [`Dockerfile`](Dockerfile) and [`railway.toml`](railway.toml). The pre-deploy command
applies the schema; the same image runs `crickops-api` and `crickops-worker`. Liveness is
`/health/live`; readiness is `/health/ready`. See the
[`judging runbook`](docs/demo/judging-availability-runbook.md) and
[`deployment evidence`](docs/evidence/deployment-gate.md).

## Privacy and limits

Guest workspaces expire after a seven-day sliding inactivity period. Do not enter personal,
confidential, financial, or payment information. Version 1 has no authentication, collaboration,
scoring, standings, DLS, external publishing, stakeholder messaging, worldwide ground discovery,
or official weather/safety decisions. Full boundaries are in [`scope.md`](scope.md).
