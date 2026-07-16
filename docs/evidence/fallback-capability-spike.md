# TASK-004 fallback-provider capability spike evidence

Date: 2026-07-16

Status: **Passed with the fallback-model layer explicitly disabled and
deterministic mode selected.**

## Documentation baseline

The official OpenAI Agents SDK
[model-provider documentation](https://openai.github.io/openai-agents-python/models/#non-openai-models)
supports non-OpenAI integration through a custom client, per-run
`ModelProvider`, per-agent model objects, or third-party adapters. The same
documentation warns that provider feature support differs and must be validated.
CrickOps therefore does not enable a provider based on credentials alone.

## Configuration outcome

- `FALLBACK_PROVIDER`: not configured.
- `FALLBACK_MODEL`: not configured.
- `FALLBACK_API_KEY`: not configured.
- Fallback-model mode: disabled.
- Active continuity path after primary-provider failure: deterministic mode.
- Fabricated conversational response: prohibited and not produced.

This is an allowed TASK-004 outcome: a fallback provider must either pass the
complete compatibility gate or remain disabled in favor of deterministic mode.

## Safety matrix

Command:

```powershell
uv run python apps/api/spikes/fallback_provider.py
```

| Case | Result | Protection demonstrated |
|---|---|---|
| Valid shared schema | Accepted by gate | Same application-level schema and explicit approval field |
| Invalid schema | Rejected | Provider output cannot bypass Pydantic validation |
| Unsupported tool | Rejected | Missing tool capability disables fallback |
| Timeout | Rejected | No fabricated response; deterministic mode remains available |
| Hard-constraint override | Rejected | Model output cannot relax confirmed hard constraints |

The executable report returned:

- `mode`: `deterministic`;
- `fallback_enabled`: `false`;
- `fabricated_response`: `false`;
- the valid case accepted and all four unsafe cases rejected.

## Automated evidence

Seven focused tests verify the shared schema gate, invalid-schema rejection,
unsupported-tool rejection, timeout rejection, hard-constraint protection,
deterministic-mode selection, non-fabrication, and fail-closed partial
configuration.

## Decision

Version 1 retains the generic provider boundary described in `spec.md`, but no
fallback model is enabled until an actual provider/model/credential combination
passes the same live matrix. Primary OpenAI failure therefore proceeds to the
required deterministic degraded mode rather than an unverified model.
