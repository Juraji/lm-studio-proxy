# LM Studio Proxy

## Project Goal

The **LM Studio Proxy** is a lightweight FastAPI application that forwards OpenAI‑compatible API requests to one or more
local LM Studio instances. It lets developers experiment with different model deployments behind a single, familiar
endpoint.

### Key Features

- Routes `/v1/*` endpoints (the standard OpenAI style) to the appropriate LM Studio instance based on the `model` field
  in the request body or a fallback configuration.
- Exposes `/v1/models` to list all models available across configured instances.
- Simple error handling that mirrors OpenAI’s response format.
- Built with minimal dependencies so it can run quickly in CI/CD pipelines or locally.

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
5. **Configure LM Studio instances** – edit `config.yaml` (a minimal example is provided below).
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

Edit `config.yaml` to define your LM Studio instances:

```yaml
instances:
  - name: local-model-1
    base_url: http://localhost:1234/v1
    models:
      - gpt-3.5-turbo
  - name: secondary-model
    base_url: http://localhost:5678/v1
    models:
      - text-davinci-003
fallback_instance: local-model-1
```

**Configuration fields:**
- `name`: Human-readable identifier for the instance
- `base_url`: LM Studio OpenAI-compatible base URL (must end with `/v1`)
- `models`: List of model names hosted by this instance
- `fallback_instance`: Optional default instance if no model match is found

### Running the Proxy

Start the proxy server:
```bash
uvicorn main:app --reload
```

The proxy will be available at `http://localhost:8000` (default Uvicorn port).

### Making Requests

Send OpenAI-compatible requests to the proxy endpoint. The proxy automatically routes requests based on the `model` field:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Testing

Run the test suite:
```bash
pytest
```

All tests use `httpx.TestClient` to verify routing, fallback behavior, and streaming support without requiring actual LM Studio instances.

### Health Check

A health check endpoint is available at `/health` for monitoring:

```bash
curl http://localhost:8000/health
```

### Example `config.yaml`

```yaml
instances:
  - name: local-model-1
    base_url: http://localhost:1234/v1
    models:
      - gpt-3.5-turbo
  - name: secondary-model
    base_url: http://localhost:5678/v1
    models:
      - text-davinci-003
fallback_instance: local-model-1
```

Feel free to add, remove or modify instances as needed for your experiments.
