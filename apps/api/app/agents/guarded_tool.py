from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from agents import FunctionTool

from app.agents.schemas import (
    AgentRole,
    ToolOutcome,
    ToolOutcomeStatus,
    ValidationStatus,
)


class ToolAuthorizationError(PermissionError):
    pass


class ToolValidationError(ValueError):
    pass


@dataclass(slots=True)
class AgentToolContext:
    role: AgentRole
    provider: str
    model: str
    tool_outcomes: list[ToolOutcome] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GuardedToolPolicy:
    authorized_roles: frozenset[AgentRole]
    deterministic_authority: bool
    output_validator: Callable[[object], bool]

    def __post_init__(self) -> None:
        if not self.authorized_roles:
            raise ValueError("guarded tools require at least one authorized role")


def _digest(value: object) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()


def guard_function_tool(tool: FunctionTool, policy: GuardedToolPolicy) -> FunctionTool:
    original_invoke = tool.on_invoke_tool

    async def guarded_invoke(context: Any, input_json: str) -> Any:
        execution_context = context.context
        if not isinstance(execution_context, AgentToolContext):
            raise ToolAuthorizationError("guarded tool requires an AgentToolContext")
        if execution_context.role not in policy.authorized_roles:
            execution_context.tool_outcomes.append(
                ToolOutcome(
                    tool_name=tool.name,
                    status=ToolOutcomeStatus.REJECTED,
                    deterministic_authority=policy.deterministic_authority,
                    validation_status=ValidationStatus.INVALID,
                    detail="role is not authorized for this tool",
                )
            )
            raise ToolAuthorizationError(
                f"{execution_context.role} is not authorized to invoke {tool.name}"
            )
        try:
            output = await original_invoke(context, input_json)
        except Exception as error:
            execution_context.tool_outcomes.append(
                ToolOutcome(
                    tool_name=tool.name,
                    status=ToolOutcomeStatus.ERROR,
                    deterministic_authority=policy.deterministic_authority,
                    validation_status=ValidationStatus.INVALID,
                    detail=type(error).__name__,
                )
            )
            raise
        if not policy.output_validator(output):
            execution_context.tool_outcomes.append(
                ToolOutcome(
                    tool_name=tool.name,
                    status=ToolOutcomeStatus.REJECTED,
                    deterministic_authority=policy.deterministic_authority,
                    validation_status=ValidationStatus.INVALID,
                    output_digest=_digest(output),
                    detail="tool output failed deterministic validation",
                )
            )
            raise ToolValidationError(f"{tool.name} output failed validation")
        execution_context.tool_outcomes.append(
            ToolOutcome(
                tool_name=tool.name,
                status=ToolOutcomeStatus.VALIDATED,
                deterministic_authority=policy.deterministic_authority,
                validation_status=ValidationStatus.VALID,
                output_digest=_digest(output),
            )
        )
        return output

    return replace(tool, on_invoke_tool=guarded_invoke)
