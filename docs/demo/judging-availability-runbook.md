# Judging availability runbook

Monitor the endpoints in [`uptime-monitor.json`](uptime-monitor.json) from submission through the
announced judging end.

- App failure: verify Vercel deployment and `crickops.vercel.app` alias.
- API failure: inspect Railway build/runtime logs and latest successful image.
- Readiness failure: diagnose the named critical dependency.
- Worker failure: restart once, inspect database connectivity, and verify retention logs.
- Provider incident: enable the disclosed deterministic emergency switch; never fabricate output.
- Weather incident: use deterministic demo weather and retain risk-guidance wording.

Daily smoke: open signed-out, load the international sample, visit setup/options/schedule/recovery/
diff/activity, verify both health endpoints, secure cookies, no private caching, and record outcome.

| Date | App | API | Worker | Hero | Incident |
|---|---|---|---|---|---|
| 2026-07-17 | Pass | Pass | Pass | Pass | None |

Never record secrets, cookie values, database URLs, personal data, or raw prompts here.

