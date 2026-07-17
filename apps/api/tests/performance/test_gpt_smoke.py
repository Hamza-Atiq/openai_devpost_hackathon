from __future__ import annotations

from performance.gpt_smoke import _failed_report, _safe_error_details, run_gpt_smoke


def test_gpt_smoke_reports_missing_key_without_fabricating_results(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    report = run_gpt_smoke()

    assert report == {
        "schema_version": "gpt-smoke/v1",
        "status": "missing_api_key",
        "model": "gpt-5.6",
        "genuine_model_calls": 0,
        "validated_roles": [],
        "fabricated_response": False,
    }


def test_safe_error_details_exposes_diagnostic_fields_without_secrets() -> None:
    error = RuntimeError("Unsupported parameter for sk-secret-example")
    error.status_code = 400  # type: ignore[attr-defined]
    error.code = "unsupported_parameter"  # type: ignore[attr-defined]
    error.param = "temperature"  # type: ignore[attr-defined]

    assert _safe_error_details(error) == {
        "error_type": "RuntimeError",
        "error_status": 400,
        "error_code": "unsupported_parameter",
        "error_param": "temperature",
        "error_message": "Unsupported parameter for [REDACTED]",
    }


def test_failed_report_preserves_completed_roles_and_failing_role() -> None:
    report = _failed_report(
        ValueError("invalid output"),
        validated_roles=["rules_constraint"],
        failing_role="scheduling_strategy",
    )

    assert report["genuine_model_calls"] == 1
    assert report["validated_roles"] == ["rules_constraint"]
    assert report["failing_role"] == "scheduling_strategy"
