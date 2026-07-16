from __future__ import annotations

from dataclasses import dataclass

from agents import ModelProvider, OpenAIProvider
from pydantic import BaseModel

from app.agents.schemas import AgentDecision, AgentMode, DeterministicModeResult


class ProviderCapabilities(BaseModel):
    structured_outputs: bool
    function_tools: bool
    validation_gate: bool
    approval_gate: bool
    hard_constraint_protection: bool

    @property
    def compatible(self) -> bool:
        return all(
            (
                self.structured_outputs,
                self.function_tools,
                self.validation_gate,
                self.approval_gate,
                self.hard_constraint_protection,
            )
        )


class ProviderRegistration(BaseModel):
    provider: str
    model: str
    capabilities: ProviderCapabilities
    sdk_provider: ModelProvider

    model_config = {"arbitrary_types_allowed": True}


@dataclass(frozen=True, slots=True)
class ProviderRoute:
    mode: AgentMode
    provider: str
    model: str
    capabilities: ProviderCapabilities
    sdk_provider: ModelProvider | None
    output_schema: type[AgentDecision] = AgentDecision

    def validate_output(self, value: object) -> AgentDecision:
        decision = self.output_schema.model_validate(value)
        if decision.provider != self.provider or decision.model != self.model:
            raise ValueError("agent decision provenance does not match the active provider route")
        return decision


_REQUIRED_CAPABILITIES = ProviderCapabilities(
    structured_outputs=True,
    function_tools=True,
    validation_gate=True,
    approval_gate=True,
    hard_constraint_protection=True,
)


class AgentProviderRouter:
    def __init__(
        self,
        *,
        openai_api_key: str,
        fallback: ProviderRegistration | None = None,
    ) -> None:
        if not openai_api_key:
            raise ValueError("an OpenAI API key is required for primary agent mode")
        if fallback is not None and not fallback.capabilities.compatible:
            raise ValueError("fallback provider did not pass the capability gate")
        self._primary_provider = OpenAIProvider(
            api_key=openai_api_key,
            use_responses=True,
            strict_feature_validation=True,
        )
        self._fallback = fallback

    def primary(self) -> ProviderRoute:
        return ProviderRoute(
            mode=AgentMode.GPT_5_6,
            provider="openai",
            model="gpt-5.6",
            capabilities=_REQUIRED_CAPABILITIES,
            sdk_provider=self._primary_provider,
        )

    def fallback(self) -> ProviderRoute:
        if self._fallback is None:
            raise RuntimeError("no compatible fallback provider is configured")
        return ProviderRoute(
            mode=AgentMode.FALLBACK_MODEL,
            provider=self._fallback.provider,
            model=self._fallback.model,
            capabilities=self._fallback.capabilities,
            sdk_provider=self._fallback.sdk_provider,
        )

    @staticmethod
    def deterministic_result(reason: str) -> DeterministicModeResult:
        return DeterministicModeResult(reason=reason)
