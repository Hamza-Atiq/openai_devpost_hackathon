from __future__ import annotations

import hmac

from fastapi import Request

from app.api.problems import APIProblem

CSRF_COOKIE_NAME = "__Host-crickops_csrf"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def validate_bootstrap_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    required = bool(getattr(request.app.state, "csrf_required", False))
    if origin is None and not required:
        return
    allowed_origins = getattr(request.app.state, "allowed_origins", frozenset())
    if origin is None or origin.rstrip("/") not in allowed_origins:
        raise APIProblem(
            status=403,
            code="origin_not_allowed",
            title="Request origin is not allowed",
            detail="Start the guest workspace from the configured CrickOps web application.",
        )


def validate_workspace_mutation(request: Request, expected_token: str) -> None:
    if request.method.upper() in _SAFE_METHODS:
        return
    origin = request.headers.get("Origin")
    required = bool(getattr(request.app.state, "csrf_required", False)) or origin is not None
    if not required:
        return
    allowed_origins = getattr(request.app.state, "allowed_origins", frozenset())
    if origin is None or origin.rstrip("/") not in allowed_origins:
        raise APIProblem(
            status=403,
            code="origin_not_allowed",
            title="Request origin is not allowed",
            detail="This mutation must originate from the configured CrickOps web application.",
        )
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get("X-CSRF-Token")
    if (
        cookie_token is None
        or header_token is None
        or not hmac.compare_digest(cookie_token, expected_token)
        or not hmac.compare_digest(header_token, expected_token)
    ):
        raise APIProblem(
            status=403,
            code="csrf_validation_failed",
            title="CSRF validation failed",
            detail="Refresh the workspace and retry the action.",
            retryable=True,
        )
