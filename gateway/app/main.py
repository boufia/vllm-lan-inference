"""FastAPI gateway: auth, rate limit, proxy to vLLM."""
import asyncio
import logging
import time
from collections import defaultdict

import httpx
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import (
    VLLM_BASE_URL,
    API_KEYS,
    VLLM_API_KEY,
    RATE_LIMIT_RPM,
    MAX_CONCURRENT_REQUESTS,
)
from .metrics import TrackedSemaphore, get_metrics_bytes, get_metrics_content_type
from .logging_config import RequestLoggingMiddleware

# One JSON line per request to stdout
_logger = logging.getLogger("llm_gateway")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_h)

app = FastAPI(title="LLM API Gateway", version="1.0.0")

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Concurrency cap for vLLM; tracked for Prometheus
vllm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
tracked_semaphore = TrackedSemaphore(vllm_semaphore)

# Rate limit: per API key, sliding window (timestamps in last 60s)
_rate_ts: defaultdict[str, list] = defaultdict(list)
RATE_WINDOW = 60.0


def _get_api_key(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("X-API-Key")


def _rate_limit(key: str) -> None:
    now = time.monotonic()
    window = _rate_ts[key]
    window[:] = [t for t in window if now - t < RATE_WINDOW]
    if len(window) >= RATE_LIMIT_RPM:
        raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": "60"})
    window.append(now)


class AuthAndRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in ("/health", "/metrics", "/docs", "/openapi.json", "/redoc", "/"):
            return await call_next(request)
        key = _get_api_key(request)
        if not key:
            if API_KEYS:
                raise HTTPException(401, "Missing API key (Authorization: Bearer <key> or X-API-Key)")
            key = "no-auth"
        elif API_KEYS and key not in API_KEYS:
            raise HTTPException(401, "Invalid API key")
        _rate_limit(key)
        request.state.api_key = key
        return await call_next(request)


app.add_middleware(AuthAndRateLimitMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    """Prometheus scrape endpoint."""
    return PlainTextResponse(
        get_metrics_bytes(),
        media_type=get_metrics_content_type(),
    )


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def proxy_v1(request: Request, path: str):
    """Proxy /v1/* to vLLM (chat/completions, completions, models, etc.)."""
    url = f"{VLLM_BASE_URL}/v1/{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

    body = None
    stream_requested = False
    if request.method == "POST" and request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
            stream_requested = isinstance(body, dict) and body.get("stream") is True
        except Exception:
            raise HTTPException(400, "Invalid JSON body")

    if request.method == "GET":
        async with tracked_semaphore.acquire():
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.get(url, headers=headers)
        if r.status_code >= 400:
            return Response(content=r.content, status_code=r.status_code, media_type="application/json")
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type", "application/json"))

    if stream_requested:
        async def stream_chunks():
            async with tracked_semaphore.acquire():
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", url, json=body, headers=headers) as r:
                        if r.status_code >= 400:
                            content = await r.aread()
                            yield content
                            return
                        async for chunk in r.aiter_bytes():
                            yield chunk
        return StreamingResponse(stream_chunks(), media_type="text/event-stream")

    async with tracked_semaphore.acquire():
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=body, headers=headers)
    if r.status_code >= 400:
        return Response(content=r.content, status_code=r.status_code, media_type="application/json")
    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type", "application/json"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
