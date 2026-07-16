from __future__ import annotations

import pytest
from pydantic import ValidationError
from spikes.openai_capabilities import (
    CapabilityReport,
    format_failure,
    require_api_key,
    validate_capability_report,
)


def valid_report() -> CapabilityReport:
    return CapabilityReport(
        model_id="gpt-5.6-sol",
        sdk_version="0.18.2",
        trace_id="trace_0123456789abcdef0123456789abcdef",
        schema_valid=True,
        tool_called=True,
        tool_result=8,
        session_persisted=True,
        latency_seconds=2.5,
        safety_timeout_seconds=30.0,
        limitations=[],
    )


def test_api_key_is_required_without_exposing_a_value() -> None:
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        require_api_key({})

    assert require_api_key({"OPENAI_API_KEY": "  secret-value  "}) == "secret-value"


def test_complete_capability_report_passes_validation() -> None:
    report = valid_report()

    validate_capability_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_valid", False),
        ("tool_called", False),
        ("tool_result", 7),
        ("session_persisted", False),
    ],
)
def test_required_capability_failure_stops_the_spike(field: str, value: object) -> None:
    report = valid_report().model_copy(update={field: value})

    with pytest.raises(RuntimeError, match="capability spike failed"):
        validate_capability_report(report)


def test_directional_latency_target_is_recorded_without_failing_capabilities() -> None:
    report = valid_report().model_copy(update={"latency_seconds": 30.1})

    validate_capability_report(report)


def test_unlabelled_timeout_has_an_actionable_failure_message() -> None:
    assert format_failure(TimeoutError()) == "TimeoutError: no message"


def test_trace_id_must_use_the_agents_sdk_shape() -> None:
    with pytest.raises(ValidationError, match="trace_id"):
        CapabilityReport.model_validate(
            valid_report().model_dump() | {"trace_id": "not-a-trace"}
        )
