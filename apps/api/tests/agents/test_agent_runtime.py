from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.agents.provider import AgentProviderRouter
from app.agents.runtime import DirectorRuntime
from app.agents.schemas import AgentMode
from app.api.workspace import GuestWorkspaceStore
from app.domain.samples import load_sample


def test_director_runtime_executes_agents_sdk_runner_with_primary_provider() -> None:
    calls: list[dict[str, object]] = []

    async def runner(agent, input_value, **kwargs):
        calls.append(
            {
                "agent": agent,
                "input": input_value,
                "max_turns": kwargs["max_turns"],
                "run_config": kwargs["run_config"],
            }
        )
        return SimpleNamespace(
            final_output={
                "message": "Review the evening-slot preference in structured controls.",
                "proposed_state_changes": [
                    {
                        "field": "priorities.preferred_slots",
                        "proposed_value": "evening",
                        "requires_confirmation": True,
                    }
                ],
                "specialist_requests": [],
                "evidence_refs": [
                    {
                        "evidence_id": "workspace-current",
                        "evidence_kind": "workspace_summary",
                        "revision": 0,
                        "consumed_fields": ["priorities", "slots"],
                    }
                ],
                "ui_actions": [
                    {
                        "action": "review_constraints",
                        "target_id": None,
                        "label": "Review interpreted constraints",
                    }
                ],
            }
        )

    store = GuestWorkspaceStore()
    _token, workspace = store.create(load_sample("global-community-cup"))
    runtime = DirectorRuntime(
        provider_router=AgentProviderRouter(openai_api_key="test-key-long-enough"),
        runner=runner,
    )

    result = asyncio.run(
        runtime.run_turn(
            workspace=workspace,
            user_message="Prefer evening matches where possible.",
        )
    )

    assert result.mode is AgentMode.GPT_5_6
    assert result.provider == "openai"
    assert result.model == "gpt-5.6"
    assert result.message and "structured controls" in result.message
    assert calls[0]["agent"].name == "Tournament Director"
    assert calls[0]["max_turns"] == 8
    assert calls[0]["run_config"].trace_include_sensitive_data is False
    assert calls[0]["run_config"].model_provider is not None
