from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from app.observability.recorder import ObservabilityRecorder


_correlation_id: ContextVar[str | None] = ContextVar("crickops_correlation_id", default=None)
_recorder: ContextVar[ObservabilityRecorder | None] = ContextVar(
    "crickops_observability_recorder",
    default=None,
)


def validated_correlation_id(candidate: str | None) -> str:
    if candidate:
        try:
            parsed = UUID(candidate)
            if str(parsed) == candidate.lower():
                return str(parsed)
        except (ValueError, AttributeError):
            pass
    return str(uuid4())


def current_correlation_id() -> str:
    return _correlation_id.get() or str(uuid4())


def current_recorder() -> ObservabilityRecorder | None:
    return _recorder.get()


@contextmanager
def observation_scope(
    correlation_id: str,
    recorder: ObservabilityRecorder,
) -> Iterator[None]:
    correlation_token = _correlation_id.set(validated_correlation_id(correlation_id))
    recorder_token = _recorder.set(recorder)
    try:
        yield
    finally:
        _recorder.reset(recorder_token)
        _correlation_id.reset(correlation_token)
