from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agents import ModelProvider
from app.agents.provider import (
    AgentProviderRouter,
    ProviderCapabilities,
    ProviderRegistration,
)
from app.agents.schemas import (
    AgentDecision,
    AgentMode,
    DeterministicModeResult,
)
from pydantic import ValidationError

NOW = datetime(2026, 7, 16, 13, tzinfo=UTC)


class StubFallbackProvider(ModelProvider):
    def get_model(self, model_name: str | None):
        raise NotImplementedError


def _decision_payload() -> dict[str, object]:
    return {
        "role": "tournament_director",
        "provider": "openai",
        "model": "gpt-5.6",
        "occurred_at": NOW,
        "summary": "The validated options are ready for organizer review.",
        "validation_status": "valid",
        "requires_organizer_approval": True,
    }


def test_primary_route_is_explicit_gpt_5_6_with_shared_schema() -> None:
    route = AgentProviderRouter(openai_api_key="test-key-long-enough").primary()

    assert route.mode is AgentMode.GPT_5_6
    assert route.provider == "openai"
    assert route.model == "gpt-5.6"
    assert route.output_schema is AgentDecision


def test_compatible_fallback_uses_same_schema_and_protections() -> None:
    fallback = ProviderRegistration(
        provider="configured-fallback",
        model="provider-model-v1",
        capabilities=ProviderCapabilities(
            structured_outputs=True,
            function_tools=True,
            validation_gate=True,
            approval_gate=True,
            hard_constraint_protection=True,
        ),
        sdk_provider=StubFallbackProvider(),
    )
    route = AgentProviderRouter(openai_api_key="test-key-long-enough", fallback=fallback).fallback()

    assert route.mode is AgentMode.FALLBACK_MODEL
    assert route.output_schema is AgentDecision
    assert route.capabilities.hard_constraint_protection is True


def test_incompatible_fallback_is_rejected() -> None:
    fallback = ProviderRegistration(
        provider="unsafe-provider",
        model="unsafe-model",
        capabilities=ProviderCapabilities(
            structured_outputs=True,
            function_tools=False,
            validation_gate=True,
            approval_gate=True,
            hard_constraint_protection=True,
        ),
        sdk_provider=StubFallbackProvider(),
    )

    with pytest.raises(ValueError, match="capability gate"):
        AgentProviderRouter(openai_api_key="test-key-long-enough", fallback=fallback)


def test_invalid_or_hidden_reasoning_output_fails_closed() -> None:
    route = AgentProviderRouter(openai_api_key="test-key-long-enough").primary()

    with pytest.raises(ValidationError):
        route.validate_output(_decision_payload() | {"hidden_reasoning": "do not store"})


def test_outage_returns_explicit_non_fabricated_deterministic_result() -> None:
    result = AgentProviderRouter(openai_api_key="test-key-long-enough").deterministic_result(
        "Agent providers are unavailable."
    )

    assert isinstance(result, DeterministicModeResult)
    assert result.mode is AgentMode.DETERMINISTIC
    assert result.agent_response is None
    assert result.fabricated_response is False
