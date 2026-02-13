#!/bin/bash
# Stop and disable Ollama so vLLM can use the GPU.
# Run: sudo ./stop-ollama.sh
set -e
systemctl stop ollama
systemctl disable ollama
echo "Ollama stopped and disabled. You can re-enable with: sudo systemctl enable --now ollama"
