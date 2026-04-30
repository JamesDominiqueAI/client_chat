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

# Langfuse integration
try:
    from langfuse import Langfuse
    from langfuse.model import ObservationPayload
except Exception:  # pragma: no cover
    Langfuse = None
    ObservationPayload = None


_RECENT_SPANS: deque[dict[str, Any]] = deque(maxlen=50)
_TRACER_READY = False
_LANGFUSE_CLIENT: Any = None


def _ensure_tracer() -> None:
    global _TRACER_READY
    if _TRACER_READY or trace is None or TracerProvider is None:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": "customer-report-agent"}))
    if os.getenv("OTEL_CONSOLE_EXPORTER", "").strip().lower() in {"1", "true", "yes"}:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _TRACER_READY = True


def _ensure_langfuse() -> Any:
    global _LANGFUSE_CLIENT
    if _LANGFUSE_CLIENT is not None:
        return _LANGFUSE_CLIENT
    langfuse_secret = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    langfuse_public = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    if langfuse_secret and langfuse_public and Langfuse is not None:
        try:
            _LANGFUSE_CLIENT = Langfuse(public_key=langfuse_public, secret_key=langfuse_secret)
            return _LANGFUSE_CLIENT
        except Exception:  # pragma: no cover
            pass
    return None


def langfuse_trace(
    name: str,
    trace_id: str,
    input_text: str | None = None,
    output_text: str | None = None,
    metadata: dict[str, Any] | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
) -> Any:
    """Send a trace to Langfuse for full observability."""
    client = _ensure_langfuse()
    if client is None:
        return None
    
    try:
        span_params: dict[str, Any] = {
            "name": name,
            "trace_id": trace_id,
        }
        if input_text:
            span_params["input"] = input_text
        if output_text:
            span_params["output"] = output_text
        if metadata:
            span_params["metadata"] = metadata
        if start_time:
            span_params["start_time"] = start_time
        if end_time:
            span_params["end_time"] = end_time
        
        return client.trace(**span_params)
    except Exception:  # pragma: no cover
        return None


def langfuse_flush() -> None:
    """Flush pending Langfuse events."""
    client = _ensure_langfuse()
    if client:
        try:
            client.flush()
        except Exception:  # pragma: no cover
            pass


@contextmanager
def traced_span(name: str, trace_id: str, attributes: dict[str, Any] | None = None):
    _ensure_tracer()
    started_at = time.perf_counter()
    span = None
    token = None
    
    # Also attempt Langfuse trace
    langfuse_span = langfuse_trace(
        name=name,
        trace_id=trace_id,
        metadata=attributes,
        start_time=started_at,
    )
    
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
        end_at = time.perf_counter()
        duration_ms = int((end_at - started_at) * 1000)
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
        
        # Update Langfuse with output and end time
        if langfuse_span is not None:
            try:
                langfuse_span.end(output={"status": "completed", "durationMs": duration_ms})
            except Exception:  # pragma: no cover
                pass


def recent_spans() -> list[dict[str, Any]]:
    return list(_RECENT_SPANS)


def telemetry_status() -> dict[str, Any]:
    langfuse_client = _ensure_langfuse()
    return {
        "openTelemetryAvailable": trace is not None,
        "consoleExporterEnabled": os.getenv("OTEL_CONSOLE_EXPORTER", "").strip().lower() in {"1", "true", "yes"},
        "recentSpanCount": len(_RECENT_SPANS),
        "langfuseAvailable": langfuse_client is not None,
        "langfuseConfigured": bool(os.getenv("LANGFUSE_SECRET_KEY", "").strip() and os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()),
    }
