# vLLM Setup (Ollama stopped, vLLM installed)

## 1. Stop Ollama

Stopping Ollama requires sudo (password). Run in a terminal:

```bash
cd "/home/server/Documents/LLM API"
chmod +x stop-ollama.sh
sudo ./stop-ollama.sh
```

To confirm Ollama is stopped:

```bash
systemctl is-active ollama   # should print "inactive"
```

## 2. Run vLLM via Docker (recommended)

The pip install failed due to network timeout downloading PyTorch (~900 MB). Using Docker avoids that: the image includes all dependencies.

### Prerequisites

- Docker installed.
- NVIDIA Container Toolkit so Docker can use the GPU.

If Docker cannot see the GPU, run:

```bash
# Add yourself to docker group (logout/login or newgrp docker)
sudo usermod -aG docker $USER

# Install NVIDIA Container Toolkit if not already
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Test GPU in Docker
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu24.04 nvidia-smi
```

### Run vLLM

From the LLM API directory:

```bash
cd "/home/server/Documents/LLM API"
chmod +x run-vllm.sh
./run-vllm.sh
```

If you see **"permission denied"** connecting to the Docker daemon, either add your user to the `docker` group and log out/in (or run `newgrp docker`), or run with sudo:

```bash
sudo ./run-vllm.sh
```

First time will pull the image: `docker pull vllm/vllm-openai:latest` (run with sudo if needed).

First run will pull the image and download the model (Phi-3-mini by default). Then the server listens on `http://0.0.0.0:8000`.

### Test

```bash
curl http://localhost:8000/v1/models
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"microsoft/Phi-3-mini-4k-instruct","messages":[{"role":"user","content":"Hi"}],"max_tokens":50}'
```

### Optional: 7B AWQ model (better quality, fits 12GB)

```bash
export VLLM_MODEL="Qwen/Qwen2.5-7B-Instruct-AWQ"
./run-vllm.sh
# Then add --quantization awq --max-model-len 32768 --max-num-seqs 24 to the script if needed, or use a custom run.
```

## 3. Pip install (optional, after fixing network)

If you prefer a local venv and have a stable connection for large downloads:

```bash
cd "/home/server/Documents/LLM API"
python3 -m venv .venv-vllm
source .venv-vllm/bin/activate
pip install --default-timeout=600 vllm
python -m vllm.entrypoints.openai.api_server --model microsoft/Phi-3-mini-4k-instruct --host 0.0.0.0 --port 8000
```

## 4. Point clients at vLLM

Set the base URL to the OpenAI-compatible API, e.g. `http://localhost:8000/v1`, and use the same model name as served (e.g. `microsoft/Phi-3-mini-4k-instruct` or `qwen2.5-7b`).
