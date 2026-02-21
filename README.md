# LLM API — Production inference server (vLLM + gateway)

OpenAI-compatible LLM API on your LAN: **gateway** (auth, rate limit) + **vLLM** (GPU inference).

## Quick start (Docker Compose)

1. **Copy env and set API keys (optional)**

   ```bash
   cd "/home/server/Documents/LLM API"
   cp .env.example .env
   # Edit .env: set API_KEYS=sk-my-key or leave empty for no auth (dev only).
   ```

2. **Start gateway + vLLM**

   ```bash
   docker compose up -d
   ```

   - Gateway: **http://localhost:8000** (clients call this).
   - vLLM runs internally; no host port for vLLM.

3. **Test**

   ```bash
   # No auth (if API_KEYS is empty)
   curl http://localhost:8000/health
   curl http://localhost:8000/v1/models

   # With auth
   curl -H "Authorization: Bearer sk-my-key" http://localhost:8000/v1/models
   curl -H "Authorization: Bearer sk-my-key" http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"microsoft/Phi-3-mini-4k-instruct","messages":[{"role":"user","content":"Hi"}],"max_tokens":50}'
   ```

## Troubleshooting

- **"unknown or invalid runtime name: nvidia"** — The compose file no longer uses `runtime: nvidia`; it uses `deploy.resources.reservations.devices` for GPU. If the vLLM container fails to get a GPU, install the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html), then run `sudo nvidia-ctk runtime configure --runtime=docker` and `sudo systemctl restart docker`.
- **vLLM exits with "no GPU" / CUDA errors** — Ensure the host has an NVIDIA driver and the toolkit is installed; run `nvidia-smi` and `docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu24.04 nvidia-smi` to verify.

## Run without Docker Compose

- **vLLM only** (e.g. for dev): `./run-vllm.sh` (see [VLLM_SETUP.md](VLLM_SETUP.md)).
- **Gateway only** (vLLM already running on host):

  ```bash
  cd gateway
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  export VLLM_BASE_URL=http://localhost:8000
  uvicorn app.main:app --host 0.0.0.0 --port 8080
  ```

  Then use **http://localhost:8080** as the API base (or put a reverse proxy in front).

## Configuration

| Env var | Description |
|--------|-------------|
| `API_KEYS` | Comma-separated keys; required for `/v1/*` if set. Empty = no auth. |
| `VLLM_BASE_URL` | vLLM base URL (e.g. `http://vllm:8000` in compose, `http://localhost:8000` for host vLLM). |
| `VLLM_API_KEY` | Optional; set if vLLM is started with `--api-key`. |
| `RATE_LIMIT_RPM` | Requests per minute per API key (default 60). |
| `MAX_CONCURRENT_REQUESTS` | Max concurrent requests to vLLM (default 32). |
| `VLLM_MODEL` | Model name for vLLM (docker-compose; default Phi-3-mini). |

## Client usage (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-my-key",  # or omit if no auth
)
r = client.chat.completions.create(
    model="microsoft/Phi-3-mini-4k-instruct",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=50,
)
print(r.choices[0].message.content)
```

## Monitoring and logging

- **Prometheus metrics** — `GET /metrics` (no auth) exposes:
  - `llm_gateway_requests_total` — request count by method, path, status
  - `llm_gateway_request_duration_seconds` — latency histogram by method, path
  - `llm_gateway_vllm_in_flight` — current requests using the vLLM semaphore

  Scrape from Prometheus or inspect with `curl http://localhost:8000/metrics`.

- **Structured logs** — One JSON line per request to stdout (e.g. Docker logs):
  - `timestamp`, `request_id`, `method`, `path`, `status`, `duration_ms`, `api_key_hash`

## Project layout

- **gateway/** — FastAPI app: auth, rate limit, proxy to vLLM, metrics, logging.
- **docker-compose.yml** — Gateway + vLLM; gateway on port 8000.
- **run-vllm.sh** — Run vLLM alone (Docker).
- **VLLM_SETUP.md** — vLLM install and run (stop Ollama, Docker, optional pip).
