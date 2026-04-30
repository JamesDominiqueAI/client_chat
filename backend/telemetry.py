from __future__ import annotations

import os
import time
from collections import deque
from contextlib import contextmanager
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
except Exception:  # pragma: no cover
    trace = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    ConsoleSpanExporter = None


_RECENT_SPANS: deque[dict[str, Any]] = deque(maxlen=50)
_TRACER_READY = False


def _ensure_tracer() -> None:
    global _TRACER_READY
    if _TRACER_READY or trace is None or TracerProvider is None:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": "customer-report-agent"}))
    if os.getenv("OTEL_CONSOLE_EXPORTER", "").strip().lower() in {"1", "true", "yes"}:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _TRACER_READY = True


@contextmanager
def traced_span(name: str, trace_id: str, attributes: dict[str, Any] | None = None):
    _ensure_tracer()
    started_at = time.perf_counter()
    span = None
    token = None
    if trace is not None and _TRACER_READY:
        tracer = trace.get_tracer("customer-report-agent")
        span = tracer.start_span(name)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        span.set_attribute("app.trace_id", trace_id)
        token = trace.use_span(span, end_on_exit=False)
        token.__enter__()
    try:
        yield
    finally:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        _RECENT_SPANS.append(
            {
                "name": name,
                "traceId": trace_id,
                "durationMs": duration_ms,
                "attributes": attributes or {},
            }
        )
        if span is not None:
            span.set_attribute("app.duration_ms", duration_ms)
            span.end()
        if token is not None:
            token.__exit__(None, None, None)


def recent_spans() -> list[dict[str, Any]]:
    return list(_RECENT_SPANS)


def telemetry_status() -> dict[str, Any]:
    return {
        "openTelemetryAvailable": trace is not None,
        "consoleExporterEnabled": os.getenv("OTEL_CONSOLE_EXPORTER", "").strip().lower() in {"1", "true", "yes"},
        "recentSpanCount": len(_RECENT_SPANS),
    }
