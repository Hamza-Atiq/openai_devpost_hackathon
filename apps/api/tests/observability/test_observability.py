from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.main import create_app
from app.observability.context import observation_scope
from app.observability.recorder import ObservabilityRecorder, redact_metadata
from app.observability.trace_processor import MinimalLocalTraceProcessor
from fastapi.testclient import TestClient

CORRELATION_ID = "018f6c7a-9a4b-7c1d-8e2f-123456789abc"
ROOT = Path(__file__).resolve().parents[4]


def test_recursive_redaction_excludes_secrets_prompts_tokens_and_diagnostics() -> None:
    safe = redact_metadata(
        {
            "provider": "openai",
            "model": "gpt-5.6",
            "authorization": "Bearer secret",
            "raw_prompt": "private organizer request",
            "nested": {
                "api_key": "secret",
                "stack_trace": "private trace",
                "validation_status": "valid",
            },
            "items": [{"cookie": "guest-secret", "tool_name": "generate_schedule"}],
        }
    )

    assert safe == {
        "provider": "openai",
        "model": "gpt-5.6",
        "nested": {"validation_status": "valid"},
        "items": [{"tool_name": "generate_schedule"}],
    }
    serialized = str(safe).lower()
    for forbidden in ("secret", "raw_prompt", "stack_trace", "authorization", "cookie"):
        assert forbidden not in serialized


def test_structured_local_log_uses_the_same_redacted_record(
    caplog: pytest.LogCaptureFixture,
) -> None:
    recorder = ObservabilityRecorder()
    with caplog.at_level(logging.INFO, logger="crickops.observability"):
        with observation_scope(CORRELATION_ID, recorder):
            recorder.record(
                component="agent",
                event="run",
                outcome="success",
                metadata={"provider": "openai", "raw_prompt": "private request"},
            )

    payload = json.loads(caplog.records[-1].message)
    assert payload["correlation_id"] == CORRELATION_ID
    assert payload["component"] == "agent"
    assert payload["metadata"] == {"provider": "openai"}
    assert "private request" not in caplog.text


def test_http_problem_and_response_share_one_validated_correlation_id() -> None:
    app = create_app()
    client = TestClient(app, base_url="https://testserver")

    response = client.post(
        "/api/v1/workspaces",
        headers={"X-Correlation-ID": CORRELATION_ID},
        json={"sample_id": "missing-sample"},
    )

    assert response.status_code == 422
    assert response.headers["X-Correlation-ID"] == CORRELATION_ID
    assert response.json()["correlation_id"] == CORRELATION_ID
    records = app.state.observability.records_for(CORRELATION_ID)
    assert records[-1].component == "http"
    assert records[-1].outcome == "error"
    assert records[-1].metadata["status_code"] == 422


def test_observation_scope_correlates_layers_and_accumulates_metrics() -> None:
    recorder = ObservabilityRecorder()

    with observation_scope(CORRELATION_ID, recorder):
        recorder.record(
            component="agent", event="run", outcome="success", metadata={"role": "director"}
        )
        recorder.record(
            component="tool", event="invoke", outcome="validated", metadata={"tool_name": "compare"}
        )
        recorder.record(
            component="validator", event="schedule", outcome="valid", metadata={"violations": 0}
        )

    assert {record.component for record in recorder.records_for(CORRELATION_ID)} == {
        "agent",
        "tool",
        "validator",
    }
    assert recorder.metric("agent_runs_total") == 1
    assert recorder.metric("tool_invocations_total") == 1
    assert recorder.metric("validation_failures_total") == 0


def test_real_schedule_operation_resolves_by_one_correlation_id_across_layers() -> None:
    app = create_app()
    client = TestClient(app, base_url="https://testserver")
    created = client.post(
        "/api/v1/workspaces",
        json={"sample_id": "global-community-cup"},
    )
    assert created.status_code == 201
    confirmed = client.post(
        "/api/v1/constraints/confirm",
        json={
            "confirmation": True,
            "expected_revision": created.json()["tournament"]["revision"],
            "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
        },
    )
    assert confirmed.status_code == 200

    generated = client.post(
        "/api/v1/schedule-runs",
        headers={
            "Idempotency-Key": "observable-generation",
            "X-Correlation-ID": CORRELATION_ID,
        },
        json={"profiles": ["balanced", "weather_first", "fairness_first"]},
    )

    assert generated.status_code == 202
    records = app.state.observability.records_for(CORRELATION_ID)
    assert {record.component for record in records} >= {
        "http",
        "weather",
        "solver",
        "validator",
        "database",
        "audit",
    }
    assert all("raw_prompt" not in str(record.metadata).lower() for record in records)


def test_dashboard_and_runbook_cover_required_operational_signals() -> None:
    dashboard = json.loads((ROOT / "config/observability/dashboard-v1.json").read_text())
    runbook = (ROOT / "docs/observability-runbook.md").read_text()

    metric_names = {metric for panel in dashboard["panels"] for metric in panel["metrics"]}
    assert {
        "http_requests_total",
        "http_errors_total",
        "solver_runs_total",
        "validation_failures_total",
        "weather_fetches_total",
        "agent_runs_total",
        "approval_conflicts_total",
        "workspace_expirations_total",
        "hero_flow_success_total",
    } <= metric_names
    assert "correlation ID" in runbook
    assert "OpenAI trace export unavailable" in runbook
    assert "raw prompts" in runbook


def test_agents_sdk_trace_processor_mirrors_only_minimal_safe_metadata() -> None:
    recorder = ObservabilityRecorder()
    processor = MinimalLocalTraceProcessor(recorder)
    trace = SimpleNamespace(
        trace_id="trace_0123456789abcdef0123456789abcdef",
        name="CrickOps hero flow",
        group_id="workspace-pseudonym",
        metadata={"correlation_id": CORRELATION_ID, "raw_prompt": "private request"},
    )
    span = SimpleNamespace(
        trace_id=trace.trace_id,
        span_id="span_0123456789abcdef0123456789abcdef",
        parent_id=None,
        span_data=SimpleNamespace(type="agent"),
        error=None,
    )

    processor.on_trace_start(trace)
    processor.on_span_start(span)
    processor.on_span_end(span)
    processor.on_trace_end(trace)
    processor.force_flush()
    processor.shutdown()

    records = recorder.records_for(CORRELATION_ID)
    assert [record.event for record in records] == [
        "trace_start",
        "span_start",
        "span_end",
        "trace_end",
    ]
    assert records[1].metadata["span_type"] == "agent"
    assert "private request" not in str(records)
    assert "raw_prompt" not in str(records)


def test_production_app_can_add_local_processor_without_replacing_sdk_export() -> None:
    app = create_app(install_sdk_tracing=True)

    assert isinstance(app.state.sdk_trace_processor, MinimalLocalTraceProcessor)
    assert app.state.sdk_trace_processor._recorder is app.state.observability
