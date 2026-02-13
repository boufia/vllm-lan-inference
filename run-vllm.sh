#!/bin/bash
# Run vLLM OpenAI-compatible server via Docker (no pip install required).
# Requires: Docker, NVIDIA Container Toolkit, Ollama stopped.
#
# Usage:
#   ./run-vllm.sh                    # default: Phi-3-mini, port 8000
#   VLLM_MODEL=Qwen/... ./run-vllm.sh
#   VLLM_PORT=8001 ./run-vllm.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${VLLM_MODEL:-microsoft/Phi-3-mini-4k-instruct}"
PORT="${VLLM_PORT:-8000}"
CACHE_DIR="${HOME}/.cache/huggingface"
mkdir -p "$CACHE_DIR"

# Default: small model for 12GB GPU. For 7B AWQ use: Qwen/Qwen2.5-7B-Instruct-AWQ
docker run --rm -it --gpus all \
  -p "${PORT}:8000" \
  -v "${CACHE_DIR}:/root/.cache/huggingface" \
  -e "HF_TOKEN=${HF_TOKEN}" \
  vllm/vllm-openai:latest \
  --model "$MODEL" \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.88 \
  --max-model-len 4096 \
  --max-num-seqs 16
