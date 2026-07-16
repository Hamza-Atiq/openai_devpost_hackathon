# TASK-003 OpenAI capability spike evidence

Date: 2026-07-16

Status: **Passed against the production-intended OpenAI account.**

## Verified documentation baseline

- The official [GPT-5.6 Sol model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
  identifies `gpt-5.6-sol` as the concrete model ID and lists Responses API,
  structured outputs, and function calling as supported.
- The official [GPT-5.6 guide](https://developers.openai.com/api/docs/guides/latest-model)
  states that the `gpt-5.6` alias routes to `gpt-5.6-sol` and recommends the
  Responses API for reasoning, tools, and multi-turn workflows.
- The official Agents SDK documentation covers
  [Pydantic output types](https://openai.github.io/openai-agents-python/agents/#output-types),
  [function tools](https://openai.github.io/openai-agents-python/tools/#function-tools),
  [sessions](https://openai.github.io/openai-agents-python/sessions/), and
  [trace IDs](https://openai.github.io/openai-agents-python/tracing/#traces-and-spans).

## Local spike implementation

- Concrete model target: `gpt-5.6-sol`.
- Locked Agents SDK version: `openai-agents==0.18.2`.
- Script: `apps/api/spikes/openai_capabilities.py`.
- The script runs two calls in one `SQLiteSession`, requires a deterministic
  function-tool result, validates both responses with a Pydantic schema, records
  a trace ID with sensitive trace capture disabled, measures each call and total
  latency, and fails if a required capability or the total timeout fails.
- Offline validation: nine focused tests pass for credential failure, evidence
  schema validation, tool/session requirements, trace ID shape, latency-target
  semantics, and timeout failure reporting.
- Missing-key execution fails closed with a safe message and does not print a key.

## Live capability result

The final live run used the ignored local environment file only to populate the
process environment. The key was not printed, copied into evidence, or committed.
The executed command was:

```powershell
uv run python apps/api/spikes/openai_capabilities.py
```

- Model ID: `gpt-5.6-sol`.
- Agents SDK: `0.18.2`.
- Trace ID: `trace_56cc2b18719b4c9693f7e8c4d10fdf69`.
- Structured schema: valid Pydantic `SpikeOutput`.
- Structured result: team count `8` and the expected concise summary.
- Function tool: invoked successfully and returned `8`.
- Session: the second turn recalled the first-turn nonce without receiving it
  again, proving SDK session persistence for the spike.
- First run latency: `9.342` seconds.
- Second run latency: `4.434` seconds.
- Total two-turn latency: `15.327` seconds under the `90`-second safety ceiling.
- Directional 10-second interpretation target: met by each final-run turn.
- Limitation: the SDK returned and flushed the trace ID without an export error,
  but trace-dashboard visibility was not independently checked from this local
  command.

The concrete model, tool call, strict output schema, session persistence, trace
creation, and bounded latency capabilities required by TASK-003 all passed.
