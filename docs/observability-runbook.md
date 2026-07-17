# CrickOps observability runbook

Use this runbook for the Version 1 demo, preview, and production environments. Organizer audit events are a separate product record; this document concerns restricted developer observability only.

## Trace one operation

1. Copy the `X-Correlation-ID` response header or Problem Details `correlation_id`.
2. Filter application observations by that correlation ID.
3. Confirm the expected chain: HTTP → agent/provider/tool when used → weather → solver → validator → database → audit/approval.
4. Compare the validation outcome and canonical schedule evidence with the approved version. Never infer success from an agent message alone.

## Sensitive-data boundary

Structured observations retain bounded metadata such as component, event, outcome, provider/model, role, latency, validation counts, and evidence identifiers. They exclude cookies, credentials, raw prompts, hidden reasoning, tokens, tool arguments, stack traces, and full organizer free text. Do not copy organizer exports or request bodies into logs.

## OpenAI trace export unavailable

Continue the demonstration using local structured application observations. Verify provider/model, agent role, guarded tool name, deterministic validation outcome, latency, and approval evidence by correlation ID. Do not fabricate an Agents SDK trace or claim central export succeeded. Record the tracing dependency transition and recover export automatically when the health check succeeds.

## First-response checks

- Elevated HTTP errors: inspect status/code counts and dependency readiness; use the correlation ID for a representative failure.
- Solver delay or infeasibility: inspect solver duration/status, queue depth, confirmed revision, and validator evidence.
- Provider fallback: inspect circuit state, retry count, provider capability gate, and active mode; deterministic scheduling must remain available.
- Validation failures: suppress the draft, retain its digest and violation codes internally, and never expose internal diagnostics to organizers.
- Approval conflicts: verify workspace ownership, expected revision, draft validity, idempotency, and current official baseline.

## Hero-flow evidence

A successful hero run contains genuine agent participation when available, real solver output, independent validation, explicit organizer approvals, a rain repair, and audit events. Any emergency cached result must be labelled and counted separately from `hero_flow_success_total`.
