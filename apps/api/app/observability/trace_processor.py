from __future__ import annotations

from threading import Lock
from typing import Any

from agents.tracing import TracingProcessor

from app.observability.context import current_correlation_id, validated_correlation_id
from app.observability.recorder import ObservabilityRecorder


class MinimalLocalTraceProcessor(TracingProcessor):
    """Mirror non-sensitive Agents SDK lifecycle metadata to local observations."""

    def __init__(self, recorder: ObservabilityRecorder) -> None:
        self._recorder = recorder
        self._trace_correlations: dict[str, str] = {}
        self._lock = Lock()

    def _trace_correlation(self, trace: Any) -> str:
        metadata = getattr(trace, "metadata", None)
        candidate = metadata.get("correlation_id") if isinstance(metadata, dict) else None
        return validated_correlation_id(candidate or current_correlation_id())

    def on_trace_start(self, trace: Any) -> None:
        correlation_id = self._trace_correlation(trace)
        with self._lock:
            self._trace_correlations[trace.trace_id] = correlation_id
        self._recorder.record(
            component="agent",
            event="trace_start",
            outcome="started",
            correlation_id=correlation_id,
            metadata={
                "trace_id": trace.trace_id,
                "workflow_name": getattr(trace, "name", None),
                "group_id": getattr(trace, "group_id", None),
            },
        )

    def on_trace_end(self, trace: Any) -> None:
        with self._lock:
            correlation_id = self._trace_correlations.pop(
                trace.trace_id,
                self._trace_correlation(trace),
            )
        self._recorder.record(
            component="agent",
            event="trace_end",
            outcome="completed",
            correlation_id=correlation_id,
            metadata={"trace_id": trace.trace_id},
        )

    def _span_correlation(self, span: Any) -> str:
        with self._lock:
            return self._trace_correlations.get(span.trace_id, current_correlation_id())

    def _span_metadata(self, span: Any) -> dict[str, object]:
        span_data = getattr(span, "span_data", None)
        return {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "parent_id": getattr(span, "parent_id", None),
            "span_type": getattr(span_data, "type", type(span_data).__name__),
            "has_error": getattr(span, "error", None) is not None,
        }

    def on_span_start(self, span: Any) -> None:
        self._recorder.record(
            component="agent",
            event="span_start",
            outcome="started",
            correlation_id=self._span_correlation(span),
            metadata=self._span_metadata(span),
        )

    def on_span_end(self, span: Any) -> None:
        self._recorder.record(
            component="agent",
            event="span_end",
            outcome="error" if getattr(span, "error", None) is not None else "completed",
            correlation_id=self._span_correlation(span),
            metadata=self._span_metadata(span),
        )

    def force_flush(self) -> None:
        return None

    def shutdown(self) -> None:
        with self._lock:
            self._trace_correlations.clear()
