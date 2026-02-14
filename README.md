# LM Studio Proxy

## Project Goal

The **LM Studio Proxy** is a lightweight FastAPI application that forwards requests to LM Studio's native REST API v0.
It provides a unified interface to access local LLMs running in LM Studio with enhanced stats and rich model information.

### Key Features

- Proxies to LM Studio's REST API v0 (`/api/v0/*`) endpoints
- Auto-discovers models from configured LM Studio instances at startup
- Routes requests to the correct instance based on the model name
- Exposes `/api/v0/models` to list all available models from all instances
- Supports chat completions, text completions, and embeddings
- Simple error handling that mirrors LM Studio's response format
- Built with minimal dependencies so it can run quickly in CI/CD pipelines or locally

## Tech Stack

| Component             | Version / Library      |
|-----------------------|------------------------|
| Python                | 3.11+ (tested on 3.12) |
| FastAPI               | `fastapi`              |
| HTTP client           | `httpx`                |
| ASGI server           | `uvicorn[standard]`    |
| Configuration parsing | `pyyaml`               |
| Testing               | `pytest`               |

## Local Setup (Developers / Maintainers)

The project uses a virtual environment located in the repository root.

1. **Clone the repo**
   ```bash
   git clone https://github.com/yourorg/lm-studio-proxy.git
   cd lm-studio-proxy
   ```
2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   ```
3. **Activate the environment**
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
4. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
5. **Configure LM Studio** – edit `config.yaml` (a minimal example is provided below).
6. **Run the application locally**
   ```bash
   uvicorn main:app --reload
   ```
7. **Run tests**
   ```bash
   pytest
   ```

## Usage

### Configuration Format

Edit `config.yaml` to configure multiple LM Studio instances:

```yaml
instances:
  - name: local-model-1
    base_url: http://localhost:1234
  - name: secondary-model
    base_url: http://localhost:5678
fallback_instance: local-model-1
```

**Configuration fields:**
- `name`: Human-readable identifier for the instance
- `base_url`: LM Studio server base URL (without `/api/v0` suffix)
- `fallback_instance`: Optional default instance if no model match is found

### Running the Proxy

Start the proxy server:
```bash
uvicorn main:app --reload
```

The proxy will be available at `http://localhost:8000` (default Uvicorn port).

### Making Requests

Send requests to the proxy. It forwards to LM Studio's v0 API:

```bash
# List models
curl http://localhost:8000/api/v0/models

# Chat completions
curl http://localhost:8000/api/v0/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "granite-3.0-2b-instruct",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Testing

Run the test suite:
```bash
pytest
```

All tests use `httpx.TestClient` to verify routing, fallback behavior, and streaming support without requiring an actual LM Studio instance.

### Health Check

A health check endpoint is available at `/health` for monitoring:

```bash
curl http://localhost:8000/health
```

### Example `config.yaml`

```yaml
instances:
  - name: local-model-1
    base_url: http://localhost:1234
  - name: secondary-model
    base_url: http://localhost:5678
fallback_instance: local-model-1
```

### Auto-Discovery

At startup, the proxy automatically fetches the list of available models from each configured LM Studio instance by calling their `/api/v0/models` endpoint. The results are cached and used for:
- Routing requests to the correct instance based on the `model` field
- Serving the `/api/v0/models` endpoint with full model information from LM Studio

## LM Studio REST API v0 Endpoints

The proxy forwards to these LM Studio v0 endpoints:

| Endpoint                       | Description                    |
|--------------------------------|--------------------------------|
| `GET /api/v0/models`           | List all available models      |
| `GET /api/v0/models/{model}`   | Get info about a specific model|
| `POST /api/v0/chat/completions`| Chat completions               |
| `POST /api/v0/completions`     | Text completions               |
| `POST /api/v0/embeddings`     | Text embeddings                |

The v0 API includes enhanced stats such as tokens/second, time to first token (TTFT), and rich model information (loaded vs unloaded, max context, quantization, etc.).
