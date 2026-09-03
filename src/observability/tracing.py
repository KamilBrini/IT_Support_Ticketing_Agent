"""Phoenix tracing helpers for agent workflows."""

from __future__ import annotations

from contextlib import contextmanager
import json
from typing import Any, Iterator

from opentelemetry import trace

try:
    from phoenix.otel import register
except Exception:  # pragma: no cover - optional dependency path
    register = None

_TRACER = trace.get_tracer("it_support_agent")
_TRACING_INITIALIZED = False


def initialize_tracing() -> None:
    """Initialize local Phoenix tracing via phoenix.otel.register()."""
    global _TRACING_INITIALIZED
    if _TRACING_INITIALIZED:
        return

    if register is not None:
        try:
            # batch=True uses an async BatchSpanProcessor so a missing/unreachable
            # Phoenix collector cannot add per-request latency to /chat; the
            # default SimpleSpanProcessor exports (and retries) synchronously
            # on the request thread, which is unacceptable when tracing is
            # meant to degrade gracefully (NFR-004).
            register(batch=True, verbose=False)
        except Exception:
            # Keep app functional even when Phoenix is unavailable.
            pass

    _TRACING_INITIALIZED = True


def safe_preview(value: Any, max_length: int = 240) -> str:
    """Serialize and truncate values before writing span attributes."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        try:
            text = json.dumps(value, ensure_ascii=True)
        except Exception:
            text = str(value)

    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3] + "..."


def _to_span_value(value: Any) -> bool | int | float | str:
    """Convert arbitrary values to OpenTelemetry-compatible attribute types."""
    if isinstance(value, (bool, int, float, str)):
        return value
    return safe_preview(value)


@contextmanager
def traced_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
    """Create a tracing span and attach sanitized attributes."""
    initialize_tracing()
    with _TRACER.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                if value is None:
                    continue
                span.set_attribute(key, _to_span_value(value))
        yield span
