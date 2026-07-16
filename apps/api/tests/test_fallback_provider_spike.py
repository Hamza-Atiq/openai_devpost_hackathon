from __future__ import annotations

import pytest
from spikes.fallback_provider import (
    CapabilityCase,
    FallbackMode,
    FallbackProbeConfig,
    evaluate_candidate,
    run_safety_matrix,
)

VALID_CANDIDATE = {
    "summary": "Balanced remains the lower-change option.",
    "tool_name": "compare_schedules",
    "hard_constraint_changes": [],
    "requires_organizer_approval": True,
}


def test_valid_candidate_passes_the_shared_application_gate() -> None:
    result = evaluate_candidate(VALID_CANDIDATE)

    assert result.accepted is True
    assert result.case is CapabilityCase.VALID


@pytest.mark.parametrize(
    ("case", "candidate", "tool_supported", "timed_out"),
    [
        (CapabilityCase.INVALID_SCHEMA, {"summary": "missing fields"}, True, False),
        (CapabilityCase.UNSUPPORTED_TOOL, VALID_CANDIDATE, False, False),
        (CapabilityCase.TIMEOUT, VALID_CANDIDATE, True, True),
        (
            CapabilityCase.HARD_CONSTRAINT_OVERRIDE,
            VALID_CANDIDATE | {"hard_constraint_changes": ["reduce minimum rest"]},
            True,
            False,
        ),
    ],
)
def test_unsafe_provider_result_is_rejected(
    case: CapabilityCase,
    candidate: object,
    tool_supported: bool,
    timed_out: bool,
) -> None:
    result = evaluate_candidate(
        candidate,
        tool_supported=tool_supported,
        timed_out=timed_out,
    )

    assert result.accepted is False
    assert result.case is case


def test_no_configured_provider_selects_deterministic_mode_without_fabrication() -> None:
    report = run_safety_matrix({})

    assert report.mode is FallbackMode.DETERMINISTIC
    assert report.fallback_enabled is False
    assert report.fabricated_response is False
    assert {result.case: result.accepted for result in report.cases} == {
        CapabilityCase.VALID: True,
        CapabilityCase.INVALID_SCHEMA: False,
        CapabilityCase.UNSUPPORTED_TOOL: False,
        CapabilityCase.TIMEOUT: False,
        CapabilityCase.HARD_CONSTRAINT_OVERRIDE: False,
    }


def test_partial_provider_configuration_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="incomplete"):
        FallbackProbeConfig.from_env({"FALLBACK_PROVIDER": "example-provider"})
