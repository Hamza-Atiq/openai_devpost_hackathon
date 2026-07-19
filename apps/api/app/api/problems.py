from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError

from app.domain.common import DomainModel
from app.observability.context import current_correlation_id


class ProblemDetails(DomainModel):
    type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: int = Field(ge=400, le=599)
    code: str = Field(pattern=r"^[a-z0-9_]+$")
    detail: str = Field(min_length=1)
    field_errors: tuple[dict[str, object], ...] | None = None
    evidence: tuple[dict[str, object], ...] | None = None
    remedies: tuple[dict[str, object], ...] | None = None
    correlation_id: str = Field(min_length=1)
    retryable: bool


class APIProblem(Exception):
    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str,
        retryable: bool = False,
        evidence: tuple[dict[str, object], ...] | None = None,
        remedies: tuple[dict[str, object], ...] | None = None,
    ) -> None:
        self.problem = ProblemDetails(
            type=f"https://crickops.dev/problems/{code}",
            title=title,
            status=status,
            code=code,
            detail=detail,
            evidence=evidence,
            remedies=remedies,
            correlation_id=current_correlation_id(),
            retryable=retryable,
        )


def _response(problem: ProblemDetails) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
    )


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIProblem)
    async def handle_api_problem(_request: Request, error: APIProblem) -> JSONResponse:
        return _response(error.problem)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        problem = ProblemDetails(
            type="https://crickops.dev/problems/request_validation_failed",
            title="Request validation failed",
            status=422,
            code="request_validation_failed",
            detail="One or more request fields are invalid.",
            field_errors=tuple(
                {
                    "location": tuple(item["loc"]),
                    "message": item["msg"],
                    "type": item["type"],
                }
                for item in error.errors()
            ),
            correlation_id=current_correlation_id(),
            retryable=False,
        )
        return _response(problem)

    @app.exception_handler(ValidationError)
    async def handle_domain_validation(
        _request: Request,
        error: ValidationError,
    ) -> JSONResponse:
        problem = ProblemDetails(
            type="https://crickops.dev/problems/invalid_tournament",
            title="Tournament configuration is invalid",
            status=422,
            code="invalid_tournament",
            detail="The configuration violates a Version 1 product boundary.",
            field_errors=tuple(
                {
                    "location": tuple(item["loc"]),
                    "message": item["msg"],
                    "type": item["type"],
                }
                for item in error.errors()
            ),
            correlation_id=current_correlation_id(),
            retryable=False,
        )
        return _response(problem)
