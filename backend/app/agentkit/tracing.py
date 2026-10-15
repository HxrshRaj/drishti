"""OpenTelemetry tracing for agent runs.

Every agent run, model call and tool call is an OTel span carrying latency,
token counts, tool names and errors. Export is chosen from standard OTel env vars:

* OTEL_EXPORTER_OTLP_ENDPOINT set -> OTLP/HTTP exporter. Langfuse, MLflow (>=3) and
  LangSmith all accept OTLP, so pointing the endpoint (and OTEL_EXPORTER_OTLP_HEADERS)
  at one of them sends these same spans there.
* AGENTKIT_TRACE_CONSOLE=1 -> console exporter.
* otherwise no exporter; spans still exist and `InMemorySpanExporter` can be attached
  (the tests and the eval runner do this to analyse traces).
"""
from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_provider: TracerProvider | None = None
_memory: InMemorySpanExporter | None = None


def configure_tracing(service_name: str = "drishti-agentkit", in_memory: bool = False) -> TracerProvider:
    """Idempotent. Returns the provider; call `get_memory_exporter()` for spans."""
    global _provider, _memory
    if _provider is not None:
        return _provider
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    if os.environ.get("AGENTKIT_TRACE_CONSOLE") == "1":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    if in_memory:
        _memory = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(_memory))
    _provider = provider
    return provider


def get_tracer() -> trace.Tracer:
    return (_provider or configure_tracing()).get_tracer("agentkit")


def get_memory_exporter() -> InMemorySpanExporter | None:
    return _memory


def add_exporter(exporter: SpanExporter) -> None:
    (_provider or configure_tracing()).add_span_processor(SimpleSpanProcessor(exporter))


def summarize_spans(spans: list[ReadableSpan]) -> dict:
    """Aggregate a run's spans into the numbers an operator cares about."""
    out = {"model_calls": 0, "tool_calls": 0, "tool_errors": 0, "input_tokens": 0,
           "output_tokens": 0, "model_ms": 0.0, "tool_ms": 0.0}
    for s in spans:
        ms = (s.end_time - s.start_time) / 1e6
        a = s.attributes or {}
        if s.name == "agent.model_call":
            out["model_calls"] += 1
            out["model_ms"] += ms
            out["input_tokens"] += int(a.get("llm.input_tokens", 0))
            out["output_tokens"] += int(a.get("llm.output_tokens", 0))
        elif s.name == "agent.tool_call":
            out["tool_calls"] += 1
            out["tool_ms"] += ms
            if a.get("tool.error"):
                out["tool_errors"] += 1
    return out


def traced_node(name: str, fn):
    """Wrap a LangGraph node so each execution is an OTel span. A human-approval
    `interrupt()` is a pause, not a failure, so it is recorded as an attribute."""
    import functools

    @functools.wraps(fn)
    def wrapper(state, *a, **kw):
        with get_tracer().start_as_current_span("mission.node", record_exception=False,
                                                set_status_on_exception=False) as span:
            span.set_attribute("mission.node", name)
            try:
                return fn(state, *a, **kw)
            except Exception as e:  # noqa: BLE001
                if type(e).__name__ == "GraphInterrupt":
                    span.set_attribute("mission.interrupted", True)
                else:
                    span.record_exception(e)
                    span.set_attribute("mission.error", type(e).__name__)
                raise

    return wrapper
