# CrickOps deterministic evaluation corpus

Run the Version 1 corpus from the repository root:

```powershell
uv run python -m evals.run
```

Each `evals/cases/v1` record declares a stable scenario category, requirement links, and a
versioned expectation in `evals/expected/v1`. The runner executes real deterministic domain and
API paths, compares exact results, and exits non-zero on any mismatch.

The report includes hard-valid displayed-schedule/repair coverage and seeded-infeasibility blocking
rates. Browser accessibility, security, repeated deployed hero reliability, and latency evidence are
added by the subsequent quality-gate tasks rather than being inferred from this deterministic corpus.
