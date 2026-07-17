from __future__ import annotations

from performance.gpt_smoke import run_gpt_smoke


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
