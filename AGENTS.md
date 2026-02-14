# AGENTS.md - LM Studio Proxy
This file provides guidance for agentic coding agents working in this repository.

## Project Overview
LM Studio Proxy is a FastAPI application that forwards requests to LM Studio's native REST API v0 (`/api/v0/*`). It provides a unified interface to access local LLMs running in LM Studio.

### API Switch Notice
This project was originally designed to proxy to multiple OpenAI-compatible endpoints (`/v1/*`). It has since been switched to proxy to LM Studio's own REST API v0, which provides:
- Enhanced stats (tokens/second, time to first token)
- Rich model information (loaded vs unloaded, max context, quantization, architecture)
- Native LM Studio endpoints (`/api/v0/models`, `/api/v0/chat/completions`, etc.)
- Documentation: [lmstudio.ai - API v0 Models](https://lmstudio.ai/docs/developer/rest/endpoints#get-apiv0models)

### Auto-Discovery
At startup, the proxy automatically fetches the list of available models from each configured LM Studio instance and caches them. This removes the need to manually configure models in `config.yaml`. The cached models are used for:
- Routing requests to the correct instance based on the `model` field
- Serving the `/api/v0/models` endpoint with full model information from LM Studio

## Development Environment
This project uses a Python virtual environment at `./.venv`. **Always activate the venv before running any Python commands.**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Commands
### Running the Application
```bash
# Using start.sh (auto-creates venv if missing)
./start.sh

# Or directly with Python
source .venv/bin/activate
python -m main
```

### Running Tests
```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run all tests in a specific file
pytest tests/test_proxy.py -v

# Run a single test by name
pytest tests/test_proxy.py::test_health_endpoint -v

# Run tests matching a pattern
pytest -k "test_model" -v
```

### Linting and Type Checking
```bash
# Run ruff linter (included in requirements.txt)
ruff check .

# Run ruff with auto-fix
ruff check --fix .

# Type checking with mypy (if installed)
pip install mypy
mypy .
```

## Code Style Guidelines
### General Principles
- Keep code minimal and focused
- Follow existing patterns in codebase
- Use type hints where beneficial
- No comments unless explaining complex logic

### Imports
Order: `from __future__ import annotations` → Standard library → Third-party → Local project
```python
from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import FastAPI, Request

from config import ProxyConfig, InstanceConfig
```

### Naming Conventions
- Files: snake_case (e.g., `proxy.py`, `config.py`)
- Classes: PascalCase (e.g., `InstanceConfig`, `ProxyConfig`)
- Functions/variables: snake_case (e.g., `load_config`, `target_base_url`)
- Constants: SCREAMING_SNAKE_CASE (e.g., `CONFIG_FILE`)
- Private methods: prefix with underscore (e.g., `_internal_method`)

### Type Hints
- Use Python 3.10+ union syntax: `str | None` instead of `Optional[str]`
- Use `from __future__ import annotations` for forward references
- Add type hints to all function parameters and return values
- Use `Any` when type cannot be precisely specified
```python
async def forward_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    content: Any = None,
) -> httpx.Response:
```

### Formatting
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 100 characters
- Use trailing commas in multi-line collections
- One blank line between top-level definitions
```python
response = await client.request(
    method=method,
    url=str(target_url),
    headers=headers,
    content=content,
)
```

### Dataclasses
```python
from dataclasses import dataclass

@dataclass
class InstanceConfig:
    name: str
    base_url: str
```

### Error Handling
- Use FastAPI's `HTTPException` for HTTP errors
- Return errors in LM Studio format
- Handle validation errors with `@app.exception_handler(RequestValidationError)`
- Generic exceptions should return 500 with a safe message
```python
raise HTTPException(status_code=400, detail=f"Model '{model_name}' not found")
```

### Async/Await
- Use `async def` for route handlers
- Use `httpx.AsyncClient` for HTTP requests
- Properly manage client lifecycle (create on startup, close on shutdown)
- Always await async functions, never use `.result()` or `.wait()`

### Testing
- Use `pytest` with `pytest-asyncio` for async tests
- Use `fastapi.testclient.TestClient` or `httpx.AsyncClient` with `ASGITransport`
- Mock external dependencies (`httpx.AsyncClient`, config)
- Test patterns:
  - Routing to correct endpoint
  - Error handling
  - Streaming support
- Use `@pytest.fixture` for reusable test fixtures
- Mark async tests with `@pytest.mark.asyncio`
```python
@pytest.mark.asyncio
async def test_health_endpoint():
    config = ProxyConfig(instances=[InstanceConfig(name="test", base_url="http://localhost:1234")])
    app = create_app(config)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
```

### Configuration
- App configuration is in `config.yaml`, this is a user managed file
- Use dataclasses for configuration models
- Load config at module level or in lifespan

## Project Structure
```
lm-studio-proxy/
├── main.py          # Entry point, starts uvicorn
├── proxy.py         # FastAPI app and routing logic
├── config.py        # Configuration loading
├── config.yaml      # Runtime configuration
├── requirements.txt # Dependencies
├── tests/
│   ├── __init__.py
│   └── test_proxy.py
└── .venv/          # Virtual environment
```

## Key Patterns
### Forwarding Requests
The `forward_request` function forwards requests to LM Studio's v0 API endpoint (`/api/v0/*`), handling both regular and streaming responses.

### Supported Endpoints
- `GET /api/v0/models` - List all available models
- `GET /api/v0/models/{model}` - Get info about a specific model
- `POST /api/v0/chat/completions` - Chat completions
- `POST /api/v0/completions` - Text completions
- `POST /api/v0/embeddings` - Text embeddings

### Response Stats
The v0 API returns enhanced stats in responses:
- `tokens_per_second`: Generation speed
- `time_to_first_token`: TTFT in seconds
- `generation_time`: Total generation time
- `model_info`: Architecture, quantization, format, context length
- `runtime`: Runtime name and version

### Model Routing
The proxy routes requests based on model name to the appropriate LM Studio instance. If a model is not found, it falls back to the configured `fallback_instance`. If no fallback is configured and the model is unknown, return a 400 error.
