"""Structured JSON request logging."""
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .metrics import REQUESTS_TOTAL, REQUEST_DURATION

LOG = logging.getLogger("llm_gateway")


def _hash_key(key: str | None) -> str:
    if not key:
        return "none"
    return hashlib.sha256(key.encode()).hexdigest()[:8]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assigns request_id, records metrics, and logs one JSON line per request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        request.state.start_time = time.perf_counter()

        response = await call_next(request)
        duration_s = time.perf_counter() - request.state.start_time
        duration_ms = round(duration_s * 1000, 2)
        method = request.method
        path = request.url.path or ""
        status = response.status_code
        api_key = getattr(request.state, "api_key", None)
        api_key_hash = _hash_key(api_key)

        REQUESTS_TOTAL.labels(method=method, path=path, status=str(status)).inc()
        REQUEST_DURATION.labels(method=method, path=path).observe(duration_s)

        log_record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": "INFO",
            "request_id": request_id,
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": duration_ms,
            "api_key_hash": api_key_hash,
        }
        LOG.info(json.dumps(log_record))

        return response
