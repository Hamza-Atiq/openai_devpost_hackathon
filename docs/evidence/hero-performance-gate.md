# TASK-053 hero reliability and performance gate

## Solver, validator, and recovery evidence

The versioned report [`hero-reliability-v1.json`](hero-reliability-v1.json) records 20 consecutive deployed-like runs against real application services with four concurrent workers and no cached schedules.

- 20/20 complete hero flows succeeded.
- 80/80 displayed schedules and repairs passed independent hard-constraint validation.
- Every run generated Balanced, Weather-first, and Fairness-first options, approved Version 1, repaired deterministic rain with one changed and 14 preserved fixtures, and approved Version 2.
- Every run recorded meaningful role contracts for all six specialists.
- 100% of end-to-end runs completed inside the three-minute hero target.

The 10/30/15-second interpretation/generation/repair values are directional goals, not scope promises. Under four-way local CPU contention, generation met 30 seconds in 55% of runs and repair met 15 seconds in 75%. Generation p50/p95 was 29.901/38.661 seconds; repair p50/p95 was 12.465/17.563 seconds; complete hero p50/p95 was 45.768/57.631 seconds. There were no reliability failures to investigate. Production capacity is checked separately in TASK-057.

## Genuine GPT-5.6 gate

`python -m performance.gpt_smoke` runs one schema-constrained, deterministic-validator-protected call for each of the six roles. It never fabricates a normal response when the API key is absent or a provider call fails. The generated `gpt-smoke-v1.json` report is the evidence source for the live-model portion of this gate.

## Browser evidence

`tests/e2e/hero.spec.ts` traverses the public judge journey, checks the three validated profiles, official schedule, disruption, minimum-change repair, approval control, and audit timeline, and enforces the three-minute ceiling. It complements the API harness; it does not substitute static or cached fixtures for solver evidence.
