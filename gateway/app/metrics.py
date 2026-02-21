"""Prometheus metrics for the gateway."""
import asyncio
from contextlib import asynccontextmanager

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

REQUESTS_TOTAL = Counter(
    "llm_gateway_requests_total",
    "Total requests to the gateway",
    ["method", "path", "status"],
)
REQUEST_DURATION = Histogram(
    "llm_gateway_request_duration_seconds",
    "Request duration in seconds",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)
VLLM_IN_FLIGHT = Gauge(
    "llm_gateway_vllm_in_flight",
    "Number of requests currently using the vLLM semaphore",
)


class TrackedSemaphore:
    """Wraps an asyncio.Semaphore and updates VLLM_IN_FLIGHT gauge."""

    def __init__(self, semaphore: asyncio.Semaphore):
        self._sem = semaphore

    @asynccontextmanager
    async def acquire(self):
        VLLM_IN_FLIGHT.inc()
        try:
            async with self._sem:
                yield
        finally:
            VLLM_IN_FLIGHT.dec()


def get_metrics_content_type():
    return CONTENT_TYPE_LATEST


def get_metrics_bytes():
    return generate_latest()
