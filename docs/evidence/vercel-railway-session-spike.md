# TASK-005 hosted session, proxy, and cache evidence

Date: 2026-07-16

## Deployed targets

- Frontend: `https://crickops.vercel.app`
- Probe page: `https://crickops.vercel.app/spike/session`
- Same-origin API: `https://crickops.vercel.app/api/v1/spike/session`
- Railway origin: `https://crickops-api-production.up.railway.app`
- Verified frontend commit: `788ffb7`

## Production verification

The Vercel build completed, produced the `/` and `/spike/session` routes, and deployed
successfully. A browser check confirmed that the probe page is served by the production
alias. A bounded production HTTP check then verified the Vercel external rewrite and
Railway session endpoint.

Observed session response:

- HTTP status: `200`
- runtime environment: `production`
- `Cache-Control: private, no-store, max-age=0`
- `Vary: Cookie`
- cookie name: `__Host-crickops_guest_probe`
- cookie attributes: `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, no `Domain`
- only an opaque session fingerprint was returned to the browser

Two requests with the same cookie resolved to the same session. A mutation using the
same cookie, the production `Origin`, and the returned anti-CSRF token produced:

```json
{
  "status": 200,
  "same_session": true,
  "mutation_count": 1,
  "accepted_value": "production-check"
}
```

Missing or attacker origins and missing CSRF tokens are rejected by focused API tests.
Unknown mutation fields are rejected with `422`, preventing a caller-supplied workspace
identifier from crossing the guest ownership boundary.

## Cache and rewrite configuration

`apps/web/vercel.json` owns the external `/api/:path*` rewrite and explicitly sends
`x-vercel-enable-rewrite-caching: 0`. The origin also returns private `no-store` headers.

## Environment isolation

The probe signs each opaque cookie over both its random token and `CRICKOPS_ENV`.
The focused isolation test presents a production cookie to a preview-configured app and
verifies that preview rejects and rotates it. Vercel host-only cookies additionally scope
production and generated preview hostnames independently.

No separate live Vercel preview URL was provisioned during this spike. The production
path was verified live; preview isolation was verified deterministically at the application
boundary. A live preview-to-production check remains available if the quality gate requires
platform-level evidence in addition to the deterministic isolation test.

## Secret handling

Provider and cookie secrets remain Railway server variables. A temporary cookie secret
echoed by Railway during initial service creation was immediately rotated before the
successful deployment. No secret is present in frontend assets or committed configuration.
