"""Gateway configuration from environment."""
import os
from typing import Set

def _parse_api_keys(value: str | None) -> Set[str]:
    if not value or not value.strip():
        return set()
    return {k.strip() for k in value.split(",") if k.strip()}

VLLM_BASE_URL: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEYS: Set[str] = _parse_api_keys(os.getenv("API_KEYS", ""))
VLLM_API_KEY: str = os.getenv("VLLM_API_KEY", "")  # optional; if vLLM is protected
RATE_LIMIT_RPM: int = max(1, int(os.getenv("RATE_LIMIT_RPM", "60")))
MAX_CONCURRENT_REQUESTS: int = max(1, int(os.getenv("MAX_CONCURRENT_REQUESTS", "32")))
