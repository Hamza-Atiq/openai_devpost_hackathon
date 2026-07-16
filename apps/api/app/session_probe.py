"""Disposable hosted-session probe for TASK-005.

This module deliberately keeps state in memory. It validates cookie, proxy, cache,
environment-isolation, and CSRF behavior before the persistent workspace model exists.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass

from fastapi import APIRouter, Cookie, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

COOKIE_NAME = "__Host-crickops_guest_probe"
_PRIVATE_CACHE_CONTROL = "private, no-store, max-age=0"


@dataclass(frozen=True, slots=True)
class SessionProbeConfig:
    environment: str
    cookie_secret: str
    allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> SessionProbeConfig:
        environment = os.getenv("CRICKOPS_ENV", "local").strip().lower()
        cookie_secret = os.getenv("CRICKOPS_COOKIE_SECRET") or secrets.token_urlsafe(32)
        origins = tuple(
            origin.strip().rstrip("/")
            for origin in os.getenv(
                "CRICKOPS_ALLOWED_FRONTEND_ORIGINS", "http://localhost:3000"
            ).split(",")
            if origin.strip()
        )
        return cls(
            environment=environment,
            cookie_secret=cookie_secret,
            allowed_origins=origins,
        )


@dataclass(slots=True)
class _ProbeSession:
    token: str
    csrf_token: str
    mutation_count: int = 0


class MutationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=80)


class SessionProbeStore:
    def __init__(self, config: SessionProbeConfig) -> None:
        self._config = config
        self._sessions: dict[str, _ProbeSession] = {}

    def _signature(self, token: str) -> str:
        message = f"{self._config.environment}:{token}".encode()
        return hmac.new(
            self._config.cookie_secret.encode(), message, hashlib.sha256
        ).hexdigest()

    def _encode_cookie(self, token: str) -> str:
        return f"{token}.{self._signature(token)}"

    def _decode_cookie(self, value: str | None) -> str | None:
        if not value or "." not in value:
            return None
        token, signature = value.rsplit(".", 1)
        if not token or not hmac.compare_digest(signature, self._signature(token)):
            return None
        return token

    def resolve(self, cookie_value: str | None) -> tuple[_ProbeSession, bool]:
        token = self._decode_cookie(cookie_value)
        if token is not None and token in self._sessions:
            return self._sessions[token], False

        session = _ProbeSession(
            token=secrets.token_urlsafe(32),
            csrf_token=secrets.token_urlsafe(32),
        )
        self._sessions[session.token] = session
        return session, True

    def cookie_value(self, session: _ProbeSession) -> str:
        return self._encode_cookie(session.token)

    @staticmethod
    def public_id(session: _ProbeSession) -> str:
        return hashlib.sha256(session.token.encode()).hexdigest()[:16]


def _mark_private(response: Response) -> None:
    response.headers["Cache-Control"] = _PRIVATE_CACHE_CONTROL
    response.headers["Vary"] = "Cookie"


def build_session_probe_router(config: SessionProbeConfig) -> APIRouter:
    router = APIRouter(prefix="/api/v1/spike", tags=["task-005-spike"])
    store = SessionProbeStore(config)

    @router.get("/session")
    def read_session(
        response: Response,
        cookie_value: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> dict[str, str | int]:
        session, created = store.resolve(cookie_value)
        if created:
            response.set_cookie(
                key=COOKIE_NAME,
                value=store.cookie_value(session),
                max_age=3600,
                path="/",
                secure=True,
                httponly=True,
                samesite="lax",
            )
        _mark_private(response)
        return {
            "session_id": store.public_id(session),
            "csrf_token": session.csrf_token,
            "environment": config.environment,
            "mutation_count": session.mutation_count,
        }

    @router.post("/session/mutations")
    def mutate_session(
        mutation: MutationInput,
        response: Response,
        cookie_value: str | None = Cookie(default=None, alias=COOKIE_NAME),
        origin: str | None = Header(default=None),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    ) -> dict[str, str | int]:
        session, created = store.resolve(cookie_value)
        if created:
            raise HTTPException(status_code=401, detail="A valid guest session is required")
        if origin is None or origin.rstrip("/") not in config.allowed_origins:
            raise HTTPException(status_code=403, detail="Request origin is not allowed")
        if csrf_token is None or not hmac.compare_digest(csrf_token, session.csrf_token):
            raise HTTPException(status_code=403, detail="CSRF token is invalid")

        session.mutation_count += 1
        _mark_private(response)
        return {
            "session_id": store.public_id(session),
            "mutation_count": session.mutation_count,
            "accepted_value": mutation.value,
        }

    return router
