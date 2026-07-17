from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI, Request

from app.observability.context import observation_scope, validated_correlation_id
from app.observability.recorder import ObservabilityRecorder


def install_observability_middleware(
    application: FastAPI,
    recorder: ObservabilityRecorder,
) -> None:
    @application.middleware("http")
    async def correlate_and_observe(request: Request, call_next):
        correlation_id = validated_correlation_id(request.headers.get("X-Correlation-ID"))
        started = perf_counter()
        with observation_scope(correlation_id, recorder):
            response = await call_next(request)
            duration_ms = round((perf_counter() - started) * 1000, 3)
            recorder.record(
                component="http",
                event="request",
                outcome="success" if response.status_code < 400 else "error",
                metadata={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            if response.status_code == 409 and request.url.path.endswith("/approve"):
                recorder.record(
                    component="approval",
                    event="approval_conflict",
                    outcome="conflict",
                    metadata={"path": request.url.path, "status_code": response.status_code},
                )
            response.headers["X-Correlation-ID"] = correlation_id
            return response
