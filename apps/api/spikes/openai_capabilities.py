"""Live GPT-5.6 Sol and OpenAI Agents SDK capability spike.

Run from the repository root with an ``OPENAI_API_KEY`` configured in the
process environment::

    uv run python apps/api/spikes/openai_capabilities.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping
from importlib.metadata import version
from time import perf_counter
from uuid import uuid4

from agents import (
    Agent,
    ModelSettings,
    RunConfig,
    Runner,
    SQLiteSession,
    flush_traces,
    function_tool,
    trace,
)
from pydantic import BaseModel, Field

MODEL_ID = "gpt-5.6-sol"
IDEAL_SINGLE_RUN_SECONDS = 10.0
DEFAULT_TOTAL_TIMEOUT_SECONDS = 90.0
EXPECTED_TEAM_COUNT = 8

_tool_results: list[int] = []


class SpikeOutput(BaseModel):
    """Strict application-level schema returned by both live turns."""

    session_token: str
    team_count: int
    summary: str


class CapabilityReport(BaseModel):
    """Machine-readable evidence emitted by a successful spike."""

    model_id: str
    sdk_version: str
    trace_id: str = Field(pattern=r"^trace_[A-Za-z0-9]{32}$")
    schema_valid: bool
    schema_result: dict[str, object] | None = None
    tool_called: bool
    tool_result: int
    session_persisted: bool
    first_run_latency_seconds: float | None = None
    second_run_latency_seconds: float | None = None
    latency_seconds: float
    safety_timeout_seconds: float
    limitations: list[str]


@function_tool
def lookup_team_count() -> int:
    """Return the fixed Version 1 tournament team count."""

    _tool_results.append(EXPECTED_TEAM_COUNT)
    return EXPECTED_TEAM_COUNT


def require_api_key(environment: Mapping[str, str]) -> str:
    """Fail clearly when the live spike has no production-intended credential."""

    api_key = environment.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required for the live TASK-003 capability spike; "
            "configure it in the process environment and do not paste it into chat or evidence"
        )
    return api_key


def validate_capability_report(report: CapabilityReport) -> None:
    """Stop the blocking spike if any required capability is absent."""

    valid = (
        report.model_id == MODEL_ID
        and report.schema_valid
        and report.tool_called
        and report.tool_result == EXPECTED_TEAM_COUNT
        and report.session_persisted
    )
    if not valid:
        raise RuntimeError("OpenAI capability spike failed a required capability")


def format_failure(error: Exception) -> str:
    """Give silent exception types such as TimeoutError an actionable label."""

    message = str(error).strip() or "no message"
    return f"{type(error).__name__}: {message}"


def build_agent() -> Agent[None]:
    """Build the smallest agent that exercises tools and structured output."""

    return Agent(
        name="CrickOps capability spike",
        model=MODEL_ID,
        instructions=(
            "This is a capability test. Always call lookup_team_count. "
            "Return the remembered session token, the tool-provided team count, "
            "and a concise summary using the required output schema."
        ),
        tools=[lookup_team_count],
        output_type=SpikeOutput,
        model_settings=ModelSettings(
            tool_choice="lookup_team_count",
            reasoning={"effort": "low"},
            verbosity="low",
        ),
    )


async def run_live_spike(timeout_seconds: float) -> CapabilityReport:
    """Execute two traced turns to prove model, tool, schema, and session support."""

    require_api_key(os.environ)
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    _tool_results.clear()
    session_token = f"session-{uuid4().hex}"
    session = SQLiteSession(f"crickops-task-003-{uuid4().hex}")
    agent = build_agent()
    run_config = RunConfig(trace_include_sensitive_data=False)
    total_started = perf_counter()

    async def execute_turns() -> tuple[SpikeOutput, SpikeOutput, float, float, str]:
        with trace(
            "CrickOps TASK-003 capability spike",
            group_id=session.session_id,
            metadata={"model_id": MODEL_ID, "sensitive_data": "disabled"},
        ) as active_trace:
            first_started = perf_counter()
            first_result = await Runner.run(
                agent,
                (
                    f"Remember the session token {session_token}. "
                    "Call the tool and return the structured result."
                ),
                session=session,
                run_config=run_config,
            )
            first_latency = perf_counter() - first_started

            second_started = perf_counter()
            second_result = await Runner.run(
                agent,
                (
                    "Without being told the token again, recall it from this session, "
                    "call the tool, and return the structured result."
                ),
                session=session,
                run_config=run_config,
            )
            second_latency = perf_counter() - second_started

        return (
            first_result.final_output,
            second_result.final_output,
            first_latency,
            second_latency,
            active_trace.trace_id,
        )

    try:
        first, second, first_latency, second_latency, trace_id = await asyncio.wait_for(
            execute_turns(), timeout=timeout_seconds
        )
    finally:
        flush_traces()

    total_latency = perf_counter() - total_started
    schema_valid = isinstance(first, SpikeOutput) and isinstance(second, SpikeOutput)
    limitations: list[str] = []
    if first_latency > IDEAL_SINGLE_RUN_SECONDS or second_latency > IDEAL_SINGLE_RUN_SECONDS:
        limitations.append(
            "At least one turn exceeded the directional 10-second interpretation target."
        )
    limitations.append(
        "Confirm the recorded trace ID is visible in the configured OpenAI trace project."
    )

    report = CapabilityReport(
        model_id=MODEL_ID,
        sdk_version=version("openai-agents"),
        trace_id=trace_id,
        schema_valid=schema_valid,
        schema_result=second.model_dump() if isinstance(second, SpikeOutput) else None,
        tool_called=len(_tool_results) >= 2,
        tool_result=_tool_results[-1] if _tool_results else -1,
        session_persisted=(
            schema_valid
            and first.session_token == session_token
            and second.session_token == session_token
        ),
        first_run_latency_seconds=round(first_latency, 3),
        second_run_latency_seconds=round(second_latency, 3),
        latency_seconds=round(total_latency, 3),
        safety_timeout_seconds=timeout_seconds,
        limitations=limitations,
    )
    validate_capability_report(report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TOTAL_TIMEOUT_SECONDS,
        help="Safety ceiling for both live turns; directional latency misses are reported.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = asyncio.run(run_live_spike(args.timeout_seconds))
    except Exception as error:  # pragma: no cover - exercised by the live command
        print(f"TASK-003 FAILED: {format_failure(error)}", file=sys.stderr)
        return 1

    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
