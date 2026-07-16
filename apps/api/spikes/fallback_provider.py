"""Fallback-provider safety and compatibility gate for TASK-004.

This spike never enables a provider merely because credentials exist. A provider
must first pass live schema/tool checks plus the deterministic safety matrix.
Without a verified provider, the only valid result is deterministic mode.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CapabilityCase(StrEnum):
    VALID = "valid"
    INVALID_SCHEMA = "invalid_schema"
    UNSUPPORTED_TOOL = "unsupported_tool"
    TIMEOUT = "timeout"
    HARD_CONSTRAINT_OVERRIDE = "hard_constraint_override"


class FallbackMode(StrEnum):
    FALLBACK_MODEL = "fallback_model"
    DETERMINISTIC = "deterministic"


class FallbackRecommendation(BaseModel):
    """Application schema shared by any primary or fallback recommendation."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=500)
    tool_name: Literal["compare_schedules"]
    hard_constraint_changes: list[str]
    requires_organizer_approval: Literal[True]


class CapabilityCaseResult(BaseModel):
    case: CapabilityCase
    accepted: bool
    reason: str


class FallbackProbeConfig(BaseModel):
    provider: str | None = None
    model: str | None = None
    api_key: str | None = Field(default=None, repr=False)

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.model and self.api_key)

    @classmethod
    def from_env(cls, environment: Mapping[str, str]) -> FallbackProbeConfig:
        values = {
            "provider": environment.get("FALLBACK_PROVIDER", "").strip() or None,
            "model": environment.get("FALLBACK_MODEL", "").strip() or None,
            "api_key": environment.get("FALLBACK_API_KEY", "").strip() or None,
        }
        configured_values = sum(value is not None for value in values.values())
        if configured_values not in {0, len(values)}:
            raise RuntimeError("Fallback provider configuration is incomplete")
        return cls(**values)


class FallbackSpikeReport(BaseModel):
    mode: FallbackMode
    fallback_enabled: bool
    provider: str | None
    model: str | None
    fabricated_response: bool
    cases: list[CapabilityCaseResult]
    limitations: list[str]


def evaluate_candidate(
    candidate: object,
    *,
    tool_supported: bool = True,
    timed_out: bool = False,
) -> CapabilityCaseResult:
    """Apply provider-independent schema, tool, approval, and hard-rule gates."""

    if timed_out:
        return CapabilityCaseResult(
            case=CapabilityCase.TIMEOUT,
            accepted=False,
            reason="Provider exceeded the bounded timeout; no response is fabricated.",
        )
    if not tool_supported:
        return CapabilityCaseResult(
            case=CapabilityCase.UNSUPPORTED_TOOL,
            accepted=False,
            reason="Required tool calling is unsupported; fallback remains disabled.",
        )

    try:
        recommendation = FallbackRecommendation.model_validate(candidate)
    except ValidationError:
        return CapabilityCaseResult(
            case=CapabilityCase.INVALID_SCHEMA,
            accepted=False,
            reason="Response failed the shared application schema.",
        )

    if recommendation.hard_constraint_changes:
        return CapabilityCaseResult(
            case=CapabilityCase.HARD_CONSTRAINT_OVERRIDE,
            accepted=False,
            reason="Model output cannot relax or replace confirmed hard constraints.",
        )

    return CapabilityCaseResult(
        case=CapabilityCase.VALID,
        accepted=True,
        reason="Schema, tool, approval, and hard-constraint protections passed.",
    )


def run_safety_matrix(environment: Mapping[str, str]) -> FallbackSpikeReport:
    """Run all required cases and select fallback or deterministic capability mode."""

    config = FallbackProbeConfig.from_env(environment)
    valid_candidate = {
        "summary": "Balanced remains the lower-change option.",
        "tool_name": "compare_schedules",
        "hard_constraint_changes": [],
        "requires_organizer_approval": True,
    }
    cases = [
        evaluate_candidate(valid_candidate),
        evaluate_candidate({"summary": "missing required fields"}),
        evaluate_candidate(valid_candidate, tool_supported=False),
        evaluate_candidate(valid_candidate, timed_out=True),
        evaluate_candidate(
            valid_candidate | {"hard_constraint_changes": ["reduce minimum rest"]}
        ),
    ]

    expected = {
        CapabilityCase.VALID: True,
        CapabilityCase.INVALID_SCHEMA: False,
        CapabilityCase.UNSUPPORTED_TOOL: False,
        CapabilityCase.TIMEOUT: False,
        CapabilityCase.HARD_CONSTRAINT_OVERRIDE: False,
    }
    if {result.case: result.accepted for result in cases} != expected:
        raise RuntimeError("Fallback safety matrix failed")

    limitations = [
        "No live fallback provider is configured and verified for Version 1.",
        "Conversational fallback is disabled; deterministic capabilities remain available.",
    ]
    if config.configured:
        limitations[0] = (
            "Fallback credentials are present, but live provider compatibility has not passed; "
            "the provider remains disabled."
        )

    return FallbackSpikeReport(
        mode=FallbackMode.DETERMINISTIC,
        fallback_enabled=False,
        provider=config.provider,
        model=config.model,
        fabricated_response=False,
        cases=cases,
        limitations=limitations,
    )


def main() -> int:
    try:
        report = run_safety_matrix(os.environ)
    except Exception as error:
        print(f"TASK-004 FAILED: {type(error).__name__}: {error}")
        return 1
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
