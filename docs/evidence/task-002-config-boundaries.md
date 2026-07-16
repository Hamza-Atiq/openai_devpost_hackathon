# TASK-002 configuration boundaries evidence

Date: 2026-07-16

## Scope and starting point

- Isolated worktree: `C:\Users\HP\.codex\worktrees\744f\openai_devpost_hackathon`
- Branch: `feat/task-002-config-boundaries`
- Starting commit: `8f14daed12edd4908a42a0fc73e20df674714795`
- Requirements: SEC-002, DEPLOY-003, DEPLOY-006

## Boundary delivered

- Backend configuration requires an explicit runtime environment, rejects unknown
  CrickOps variables, and validates database, provider, cookie, encryption, and
  frontend-origin values.
- Preview and production fail closed when required server configuration is absent.
- Local and test modes disable live services by default; opting in requires the live
  database and provider values.
- Frontend configuration accepts only `NEXT_PUBLIC_API_BASE_URL` and
  `NEXT_PUBLIC_BUILD_SHA`; unknown and server-only names are rejected.
- `.env.example` documents server/public ownership without containing credentials.
- `.gitleaks.toml` extends the default scanner and adds a frontend artifact rule.

## Test-first evidence

- Backend RED: `uv run pytest apps/api/tests/test_settings.py apps/api/tests/test_secret_boundaries.py -q`
  failed because `app.settings` did not exist.
- Frontend RED: `pnpm.cmd --filter @crickops/web test -- lib/env.test.ts`
  failed because `lib/env.ts` did not exist.
- Focused GREEN:
  - Backend: 15 passed.
  - Frontend: 2 files, 9 tests passed (including the existing scaffold test).

## Secret-leak verification

A production Next.js build ran with representative server key names and fixture values
present only in the build process. A recursive text scan of `apps/web/.next` found none
of the following:

- `DATABASE_URL`, `OPENAI_API_KEY`, `CRICKOPS_COOKIE_SECRET`,
  `CRICKOPS_ENCRYPTION_SECRET`
- Representative database, provider, cookie, and encryption fixture values

Result: `Secret leak scan passed: no key names or fixture values found in apps/web/.next.`

## Regression gates

- `pnpm.cmd lint` — exit 0.
- `pnpm.cmd test` — 2 files, 9 tests passed.
- `uv run ruff check .` — all checks passed.
- `uv run pytest` — 21 tests passed.

TASK-002 validation passed without starting or preparing TASK-003.
