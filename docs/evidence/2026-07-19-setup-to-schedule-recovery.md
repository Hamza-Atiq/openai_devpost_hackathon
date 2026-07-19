# Setup-to-schedule recovery evidence

Date: 2026-07-19

## Outcome

The organizer setup is now backend-owned, revisioned, autosaved, and reused by genuine schedule generation. Options are tied to the generated run, and the Schedule page renders only the latest explicitly approved, independently validated backend draft.

## Defects reproduced and corrected

1. Setup controls other than T10/T20 were local uncontrolled defaults and disappeared on navigation.
2. The setup action confirmed constraints but never called `POST /api/v1/schedule-runs`.
3. Options and Schedule displayed bundled demonstration data unrelated to organizer input.
4. The first real browser run exposed read-only venue metadata being echoed into the strict save command. The client boundary now whitelists editable fields only.
5. The legacy hero browser test skipped Setup and approval by navigating directly to static routes.

## Implemented behavior

- Typed `GET/PUT /api/v1/tournament` setup contract with optimistic revision checks and idempotency.
- Deterministic slot expansion from organizer dates, weekday/weekend starts, blackouts, timezone, and T10/T20 allocation.
- Real feasibility precheck and exact-revision hard-constraint confirmation before generation.
- Browser draft recovery, 650 ms autosave, saved/dirty/saving/error states, and stale-write protection.
- Explicit **Confirm and generate schedules** workflow with confirming, solving, validating, and safe-failure feedback.
- Exactly one schedule-run request per organizer action and run-specific Options loading.
- `GET /api/v1/official-schedule` returning version metadata and the exact 15 validated placements from the latest approved draft.
- Honest empty states when no generated or official schedule exists; no production fallback fixtures.

## Fresh verification

| Gate | Result |
|---|---|
| `pnpm install --frozen-lockfile` | Passed; lockfile unchanged |
| `uv sync --frozen` | Passed; 64 packages audited |
| `pnpm lint` | Passed with zero warnings |
| `pnpm test` | 19 files, 52 tests passed |
| `uv run ruff check .` | Passed |
| `uv run pytest` | 310 passed, 1 environment-dependent PostgreSQL integration test skipped, 0 failed in 613.39 s |
| `pnpm --filter @crickops/web build` | Passed; nine application routes built |
| Focused local Playwright hero journey | Passed in 42.8 s |
| `git diff --check` | Passed; only repository line-ending notices |

The passing browser journey loaded the Pakistan sample, edited a venue, observed autosave, navigated away and back, confirmed persistence, generated all three validated profiles with one request, approved Balanced as Version 1, and verified 15 backend-owned fixtures on Schedule.

## Requirements covered

Primary traceability: FR-001–FR-018, SCHED-001–SCHED-024, APPROVAL-001–APPROVAL-007, AC-001–AC-012, NFR-002–NFR-004, DATA-001–DATA-006, ACCESS-001–ACCESS-006.

## Deployment impact and limitations

- Railway must deploy the new API before Vercel deploys the client that calls `PUT /api/v1/tournament` and `GET /api/v1/official-schedule`.
- No database migration is required; workspace snapshots already persist the added setup state.
- The public site is not claimed updated by this evidence until both deployments complete and the deployed browser journey is repeated.
- This recovery does **not** resolve the separately identified OpenAI runtime wiring gap: the deployed request path must still connect the existing six specialist roles and GPT-5.6 orchestration before the project can claim meaningful live model use or Quality Gate 19 completion.
