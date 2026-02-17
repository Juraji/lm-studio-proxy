# LM Studio Proxy

## What is it?

**LM Studio Proxy** is a lightweight FastAPI application that acts as a unified gateway to multiple LM Studio instances. Instead of managing separate connections to each LM Studio server, you get a single endpoint that automatically routes requests to the correct instance based on the model name.

### Key Features

- **Multi-Instance Aggregation** – Connect multiple LM Studio servers and expose them as one unified API
- **Auto-Discovery** – Automatically discovers available models from all instances at startup and periodically refreshes the list
- **Smart Routing** – Routes requests to the correct instance based on the `model` field in your request
- **Dual API Support** – Forwards to both LM Studio REST API v0 (`/api/v0/*`) and v1 (`/api/v1/*`) endpoints
- **Unified Models List** – `/api/v0/models` and `/api/v1/models` return all models from all instances
- **Streaming Support** – Full support for streaming chat completions
- **Health Monitoring** – Built-in `/health` endpoint for load balancers and monitoring

## Why does it exist?

I have two machines at home: a lightweight home server for lighter tasks like code completion and small queries, and a more powerful workstation for running beefy models on complex tasks. Both run LM Studio, but tools like the JetBrains AI plugin only allow a single custom endpoint.

Rather than constantly switching configs or limiting myself to one machine, I built this proxy to aggregate both LM Studio instances into a single endpoint. The proxy automatically routes requests to the right machine based on the model name – so when I use `granite-3.0-2b-instruct` it goes to my home server, but when I switch to a larger model it hits my workstation.

## User Setup

### Prerequisites

- Python 3.11 or higher
- One or more running LM Studio instances

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourorg/lm-studio-proxy.git
   cd lm-studio-proxy
   ```

2. **Configure your instances** – Edit `config.yaml`:
   ```yaml
   instances:
     - name: local-model-1
       base_url: http://localhost:1234
     - name: secondary-model
       base_url: http://localhost:5678
   fallback_instance: local-model-1
   ```

3. **Start the proxy**
   ```bash
   ./start.sh
   ```

The proxy runs on `http://localhost:8000` by default.

### Making Requests

The proxy forwards to LM Studio's native REST API. See [LM Studio REST API Docs](https://lmstudio.ai/docs/developer/rest) for the full specification.

> **Note:** This proxy supports only LM Studio's native API (`/api/v0/*` and `/api/v1/*`). It does **not** forward to OpenAI-compatible (`/v1/chat/completions`) or Anthropic-compatible (`/v1/messages`) endpoints.

```bash
# List all available models from all instances (v1)
curl http://localhost:8000/api/v1/models

# Chat completions (v1) - native LM Studio format
curl http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-3.0-2b-instruct",
    "input": "Hello!"
  }'

# Streaming chat completions (v1)
curl http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-3.0-2b-instruct",
    "input": "Hello!",
    "stream": true
  }'

# Chat completions (v0 - legacy)
curl http://localhost:8000/api/v0/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-3.0-2b-instruct",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# Health check
curl http://localhost:8000/health
```

### Configuration Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `instances` | list | Yes | List of LM Studio instances |
| `instances[].name` | string | Yes | Human-readable identifier |
| `instances[].base_url` | string | Yes | LM Studio server URL (without `/api/*` suffix) |
| `fallback_instance` | string | Yes | Default instance to use when model is not found |
| `model_discovery_reload_interval_seconds` | int | No | How often to refresh model list (default: 30, set to 0 to disable) |
| `request_timeout_seconds` | int | No | Timeout for forwarded requests (default: 5) |

### How Routing Works

1. At startup (and every 30 seconds by default), the proxy fetches the model list from each configured instance
2. When a request comes in, it extracts the `model` field from the request body
3. If the model is found in the auto-discovered list, the request is routed to that instance
4. If not found, it falls back to `fallback_instance`
5. If neither matches, the proxy returns an error

---

## Development Setup

The project uses a virtual environment located in the repository root.

1. **Create a virtual environment**
   ```bash
   python -m venv .venv
   ```

2. **Activate the environment**
   - macOS / Linux:
     ```bash
     source .venv/bin/activate
     ```
   - Windows (PowerShell):
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   - Windows (Command Prompt):
     ```cmd
     .\.venv\Scripts\activate.bat
     ```

3. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   ./start.sh
   ```

5. **Run tests**
   ```bash
   pytest
   ```

6. **Lint code**
   ```bash
   ruff check .

## Tech Stack

| Component             | Version / Library      |
|-----------------------|------------------------|
| Python                | 3.11+ (tested on 3.12) |
| FastAPI               | `fastapi`              |
| HTTP client           | `httpx`                |
| ASGI server           | `uvicorn[standard]`    |
| Configuration parsing | `pyyaml`               |
| Testing               | `pytest`               |

## LM Studio API Endpoints

The proxy forwards to these LM Studio endpoints:

### v0 API

| Endpoint                       | Description                    |
|--------------------------------|--------------------------------|
| `GET /api/v0/models`           | List all available models      |
| `GET /api/v0/models/{model}`   | Get info about a specific model|
| `POST /api/v0/chat/completions`| Chat completions               |
| `POST /api/v0/completions`     | Text completions               |
| `POST /api/v0/embeddings`     | Text embeddings                |

### v1 API

| Endpoint                       | Description                    |
|--------------------------------|--------------------------------|
| `GET /api/v1/models`           | List all available models      |
| `POST /api/v1/chat`           | Chat completions               |
| `POST /api/v1/completions`     | Text completions               |
| `POST /api/v1/embeddings`      | Text embeddings                |

The v0 API includes enhanced stats such as tokens/second, time to first token (TTFT), and rich model information (loaded vs unloaded, max context, quantization, etc.).
