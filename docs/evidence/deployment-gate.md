# Deployment gate evidence

Verified 2026-07-17 (Asia/Karachi).

## Railway

- Production services: `crickops-api`, `crickops-worker`, and managed PostgreSQL.
- API deployment `f348820a-f006-4359-b982-d8bd811c7104`: SUCCESS.
- Worker deployment `164bc438-33db-4dfa-acc9-461daedfcf8b`: SUCCESS.
- `/health/live` and `/health/ready`: HTTP 200.
- Non-root Docker image, pre-deploy schema application, private database reference, and hourly
  retention cleanup are active.
- Required variable names were checked without printing values. OpenAI, cookie, encryption,
  database, origin, and runtime configuration are present.
- Durable store tests restore mutated workspace data from a new store instance.

The schema-creating integration test is not run against production because it creates and drops an
isolated schema. Production migration success, health, read-only metadata, and disposable-database
tests provide the safe evidence path.

## Vercel

- Public URL: <https://crickops.vercel.app>.
- Next.js build succeeds from `apps/web`.
- `/api/:path*` proxies to Railway; rewrite caching is disabled.
- Workspace responses are `private, no-store` with `Vary: Cookie`.
- Invalid-origin bootstrap is rejected and guest cookies remain host-only.
- Production accessibility checks passed; the corrected real-sample hero smoke passed in 27.2s.

## Deployed behavior

Automated contracts cover guest isolation, refresh/restore, fallback, deterministic mode, deletion,
export, weather, approval, repair, audit, and hard-constraint validation. A final signed-out manual
judge walkthrough remains the user acceptance step after TASK-060.

