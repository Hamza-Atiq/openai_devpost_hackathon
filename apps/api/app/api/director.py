from __future__ import annotations

from typing import Annotated, Any, Protocol

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from app.agents.runtime import DirectorRuntimeResult
from app.agents.schemas import AgentMode
from app.api.audit import append_audit_event
from app.api.operations import OperationsState
from app.api.problems import APIProblem
from app.api.routes import require_workspace
from app.api.workspace import GuestWorkspace
from app.domain.common import DomainModel
from app.limits.public_demo import PublicDemoProtection, UsageAction


class DirectorTurnRequest(DomainModel):
    message: str = Field(min_length=1, max_length=4000)


class DirectorRuntimeProtocol(Protocol):
    async def run_turn(
        self,
        *,
        workspace: GuestWorkspace,
        user_message: str,
    ) -> DirectorRuntimeResult | dict[str, Any]: ...


def _deterministic_unavailable() -> DirectorRuntimeResult:
    return DirectorRuntimeResult(
        mode=AgentMode.DETERMINISTIC,
        attempt_count=0,
        transitions=("deterministic_active",),
        unavailable_reason=(
            "Conversational interpretation is unavailable. Structured setup, scheduling, "
            "validation, and recovery remain available."
        ),
    )


def build_director_router(
    runtime: DirectorRuntimeProtocol | None,
    state: OperationsState,
    demo_protection: PublicDemoProtection,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/director/turn")
    async def director_turn(
        body: DirectorTurnRequest,
        request: Request,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        if runtime is None:
            result = _deterministic_unavailable()
        else:
            limit = demo_protection.consume(
                UsageAction.AGENT,
                workspace_id=workspace.workspace_id,
                ip_address=request.client.host if request.client else None,
            )
            if not limit.allowed:
                raise APIProblem(
                    status=429,
                    code="public_demo_limit_exceeded",
                    title="Director capacity reached",
                    detail=(
                        "Agent conversation is temporarily limited; structured controls "
                        "remain available."
                    ),
                    retryable=True,
                )
            result = DirectorRuntimeResult.model_validate(
                await runtime.run_turn(workspace=workspace, user_message=body.message)
            )

        state.mode = result.mode
        state.provider = result.provider
        state.model = result.model
        provenance = (
            {
                "role": "tournament_director",
                "provider": result.provider,
                "model": result.model,
                "validation_status": "valid",
            }
            if result.provider and result.model
            else None
        )
        append_audit_event(
            state,
            workspace.workspace_id,
            event_type=(
                "director_turn_completed"
                if result.message is not None
                else "director_turn_unavailable"
            ),
            summary=(
                "Tournament Director interpreted an organizer request."
                if result.message is not None
                else (
                    "Tournament Director conversation was unavailable; deterministic "
                    "controls remained active."
                )
            ),
            structured_payload={
                "mode": result.mode,
                "attempt_count": result.attempt_count,
            },
            actor_type="system",
            agent_provenance=provenance,
        )
        return {
            **result.model_dump(mode="json"),
            "fabricated_agent_response": False,
        }

    return router
