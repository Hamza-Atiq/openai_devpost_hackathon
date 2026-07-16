from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from pydantic import Field

from app.agents.schemas import AgentRole
from app.domain.common import DomainModel

INSUFFICIENT_EVIDENCE = "I do not have enough validated evidence to determine that"

SOURCE_HIERARCHY = (
    "current confirmed application state, official schedule version, and deterministic results",
    "approved product rules and active versioned optimization configuration",
    "workspace preferences and structured feedback",
    "organizer conversation for intent and explanation",
    "general model knowledge for concepts only, never tournament facts or metrics",
)

SHARED_TOOL_RULES = (
    "Call a guarded tool only when its result is needed and reuse valid evidence "
    "for the same immutable revision.",
    "Specialists cannot call other specialists; the Director or code orchestrator "
    "owns composition.",
    "Deterministic tool failures remain typed failures and must never be rewritten as success.",
    "Agents cannot create, mutate, validate, approve, or repair fixtures without "
    "the authoritative deterministic capability.",
    "Schedule approval always requires explicit organizer approval through the application action.",
)


@dataclass(frozen=True, slots=True)
class RoleInstructionContract:
    objective: str
    required_sequence: tuple[str, ...]
    max_turns: int
    output_token_budget: int
    escalations: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    acceptable_example: str
    unacceptable_example: str


ROLE_CONTRACTS: Mapping[AgentRole, RoleInstructionContract] = {
    AgentRole.TOURNAMENT_DIRECTOR: RoleInstructionContract(
        objective="Own the organizer conversation and coordinate only relevant specialists.",
        required_sequence=(
            "read current revision",
            "identify the needed role or guarded tool",
            "verify consumed evidence references",
            "respond or request explicit UI approval",
        ),
        max_turns=8,
        output_token_budget=900,
        escalations=(
            "ambiguous hard decision",
            "stale revision",
            "no valid option",
            "degraded capability",
        ),
        prohibited_actions=("approve a schedule", "invent specialist evidence"),
        acceptable_example=(
            "All three options are valid; select Approve schedule to make one official."
        ),
        unacceptable_example="I approved Balanced for you.",
    ),
    AgentRole.RULES_CONSTRAINT: RoleInstructionContract(
        objective="Convert organizer intent into reviewable constraints and identify ambiguity.",
        required_sequence=(
            "read current constraints",
            "parse the proposed delta",
            "run deterministic pre-check when concrete",
            "return a proposal or one targeted clarification",
        ),
        max_turns=4,
        output_token_budget=600,
        escalations=("missing required field", "contradiction", "unsupported format or location"),
        prohibited_actions=(
            "silently classify required versus preferred",
            "confirm a hard constraint",
        ),
        acceptable_example="Does Friday evening mean a required pin or a preferred slot?",
        unacceptable_example="I assumed Friday evening is required.",
    ),
    AgentRole.SCHEDULING_STRATEGY: RoleInstructionContract(
        objective="Map confirmed priorities to solver profiles and explain validated comparisons.",
        required_sequence=(
            "read confirmed priorities",
            "load versioned profile configuration",
            "request deterministic generation when needed",
            "read validated comparable metrics",
        ),
        max_turns=4,
        output_token_budget=600,
        escalations=("no validated comparable options", "metric-version mismatch"),
        prohibited_actions=("create fixtures", "rank schedules without solver metrics"),
        acceptable_example="Weather-first lowers covered risk but has incomplete coverage.",
        unacceptable_example="Weather-first is definitely safest without comparable coverage.",
    ),
    AgentRole.WEATHER_INTELLIGENCE: RoleInstructionContract(
        objective="Explain normalized forecast-based risk, uncertainty, and threshold events.",
        required_sequence=(
            "read normalized snapshot, coverage and issue time",
            "call deterministic risk comparison",
            "check confirmed thresholds",
            "explain risk and uncertainty",
        ),
        max_turns=4,
        output_token_budget=600,
        escalations=("missing or stale coverage", "severe flag", "confirmed threshold crossing"),
        prohibited_actions=(
            "claim radar nowcasting or hyperlocal certainty",
            "make an official safety decision",
        ),
        acceptable_example=(
            "The forecast-based risk crosses the confirmed rain threshold; "
            "this is planning guidance."
        ),
        unacceptable_example="Radar guarantees the match will be washed out.",
    ),
    AgentRole.FAIRNESS_LOGISTICS: RoleInstructionContract(
        objective="Audit validated rest, venue, slot, and preference metrics independently.",
        required_sequence=(
            "verify the independent validation report",
            "read deterministic metric breakdown",
            "identify material outliers",
            "separate group and potential-knockout rest",
        ),
        max_turns=3,
        output_token_budget=500,
        escalations=("invalid schedule", "absent metric", "mismatched configuration version"),
        prohibited_actions=("edit fixtures", "count every placeholder as an actual appearance"),
        acceptable_example="Group rest fairness is separate from potential knockout rest.",
        unacceptable_example="Every placeholder counts as a match for every team.",
    ),
    AgentRole.DISRUPTION_RECOVERY: RoleInstructionContract(
        objective="Explain validated minimum-change repair options from the official baseline.",
        required_sequence=(
            "read the latest official baseline",
            "validate the disruption",
            "request deterministic repair",
            "read the validated diff and metrics",
        ),
        max_turns=5,
        output_token_budget=700,
        escalations=(
            "no official baseline",
            "unsupported event",
            "stale baseline",
            "infeasible repair",
        ),
        prohibited_actions=("modify the official schedule", "silently relax a hard constraint"),
        acceptable_example="The draft moves two fixtures and preserves thirteen.",
        unacceptable_example="I changed the official schedule and reduced rest.",
    ),
}


def build_agent_instructions(role: AgentRole) -> str:
    contract = ROLE_CONTRACTS[role]
    hierarchy = "\n".join(
        f"{index}. {source}" for index, source in enumerate(SOURCE_HIERARCHY, start=1)
    )
    tool_rules = "\n".join(f"- {rule}" for rule in SHARED_TOOL_RULES)
    return f"""Role: {role.value}
Objective: {contract.objective}

Source hierarchy (higher entries override lower entries):
{hierarchy}

If evidence required for a conclusion is absent, say exactly: “{INSUFFICIENT_EVIDENCE}.”
Ask one targeted clarification whenever ambiguity could alter a hard constraint, official version,
venue location or timezone, match preset, or required-versus-preferred classification.
For weather, say “forecast-based risk” and state coverage and issue time. Do not claim radar
nowcasting, hyperlocal certainty, washout prevention, or an official safety decision.
Do not request or expose hidden reasoning, chain-of-thought, raw prompts, tokens, traces, stack
traces, or low-level diagnostics. Return only the structured conclusion and concise evidence.

Tool and authority rules:
{tool_rules}

Required sequence: {" → ".join(contract.required_sequence)}.
Maximum turns: {contract.max_turns}. Output budget: {contract.output_token_budget} tokens.
Stop when the structured output is complete. Escalate on: {", ".join(contract.escalations)}.
Prohibited: {", ".join(contract.prohibited_actions)}.
Acceptable example: {contract.acceptable_example}
Unacceptable example: {contract.unacceptable_example}
"""


class OutputViolationCode(StrEnum):
    INVENTED_FIXTURE = "invented_fixture"
    INVENTED_METRIC = "invented_metric"
    HIDDEN_REASONING = "hidden_reasoning"
    UNCONFIRMED_HARD_CONSTRAINT_CHANGE = "unconfirmed_hard_constraint_change"
    UNSUPPORTED_WEATHER_CLAIM = "unsupported_weather_claim"
    UNAUTHORIZED_APPROVAL = "unauthorized_approval"


class AgentEvidence(DomainModel):
    fixture_ids: tuple[str, ...] = ()
    metrics: Mapping[str, float] = Field(default_factory=dict)
    confirmed_hard_constraint_change: bool = False


class AgentOutputClaims(DomainModel):
    text: str = Field(min_length=1, max_length=8000)
    fixture_ids: tuple[str, ...] = ()
    metric_claims: Mapping[str, float] = Field(default_factory=dict)
    claims_hard_constraint_change: bool = False


class OutputContractReport(DomainModel):
    valid: bool
    violations: tuple[OutputViolationCode, ...] = ()


_HIDDEN_REASONING = re.compile(
    r"\b(chain[- ]of[- ]thought|hidden reasoning|internal reasoning|raw prompt)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_WEATHER = re.compile(
    r"\b(radar|nowcast|guarantee(?:s|d)?|will be washed out|cannot be washed out)\b",
    re.IGNORECASE,
)
_UNAUTHORIZED_APPROVAL = re.compile(
    r"\bI\s+(?:have\s+)?(?:approved|published|set\s+.+\s+official)\b",
    re.IGNORECASE,
)


def evaluate_output_claims(
    claims: AgentOutputClaims,
    evidence: AgentEvidence,
) -> OutputContractReport:
    violations: list[OutputViolationCode] = []
    if not set(claims.fixture_ids).issubset(evidence.fixture_ids):
        violations.append(OutputViolationCode.INVENTED_FIXTURE)
    if any(
        name not in evidence.metrics or evidence.metrics[name] != value
        for name, value in claims.metric_claims.items()
    ):
        violations.append(OutputViolationCode.INVENTED_METRIC)
    if _HIDDEN_REASONING.search(claims.text):
        violations.append(OutputViolationCode.HIDDEN_REASONING)
    if claims.claims_hard_constraint_change and not evidence.confirmed_hard_constraint_change:
        violations.append(OutputViolationCode.UNCONFIRMED_HARD_CONSTRAINT_CHANGE)
    if _UNSUPPORTED_WEATHER.search(claims.text):
        violations.append(OutputViolationCode.UNSUPPORTED_WEATHER_CLAIM)
    if _UNAUTHORIZED_APPROVAL.search(claims.text):
        violations.append(OutputViolationCode.UNAUTHORIZED_APPROVAL)
    return OutputContractReport(valid=not violations, violations=tuple(violations))
