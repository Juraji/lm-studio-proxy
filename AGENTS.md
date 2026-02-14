# AGENTS.md - LM Studio Proxy
This file provides guidance for agentic coding agents working in this repository.

## Project Overview
LM Studio Proxy is a FastAPI application that forwards OpenAI-compatible API requests to one or more local LM Studio instances. It routes requests based on the `model` field in the request body.

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
```

### Running Tests
```bash
pytest
pytest tests/test_proxy.py::test_routing
pytest tests/test_proxy.py::test_streaming
pytest tests/test_proxy.py::test_multiple_apis
pytest -v
```

### Running with Python directly
```bash
source .venv/bin/activate
python -m main
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
from typing import Dict, Optional
import httpx
from fastapi import FastAPI, Request

from config import load_config, InstanceConfig
```

### Naming Conventions
- Files: snake_case (e.g., `proxy.py`, `config.py`)
- Classes: PascalCase (e.g., `InstanceConfig`, `ProxyConfig`)
- Functions/variables: snake_case (e.g., `load_config`, `target_base_url`)
- Constants: SCREAMING_SNAKE_CASE (e.g., `CONFIG_FILE`)

### Type Hints
- Use Python 3.10+ union syntax: `str | None` instead of `Optional[str]`
- Use `from __future__ import annotations` for forward references
- Add type hints to function parameters and return values

### Dataclasses
```python
from dataclasses import dataclass, field

@dataclass
class InstanceConfig:
    name: str
    base_url: str
    models: List[str] = field(default_factory=list)
```

### Error Handling
- Use FastAPI's `HTTPException` for HTTP errors
- Return errors in OpenAI format: `{"error": {"message": "..."}}`
- Handle validation errors with `@app.exception_handler(RequestValidationError)`
- Generic exceptions should return 500 with a safe message
```python
raise HTTPException(status_code=400, detail=f"Model '{model_name}' not found and no fallback defined")
```

### Async/Await
- Use `async def` for route handlers
- Use `httpx.AsyncClient` for HTTP requests
- Properly manage client lifecycle (create on startup, close on shutdown)

### Testing
- Use `pytest` for testing
- Use `fastapi.testclient.TestClient` for endpoint testing
- Mock external dependencies (`httpx.AsyncClient`, config)
- Test patterns:
  - Routing to correct instance based on model
  - Fallback behavior when model not found
  - Streaming support
  - Multiple API instances

### Configuration
- App configuration is in `config.yaml`, this is a user managed file.
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
The `forward_request` function strips `/v1` prefix, forwards to target LM Studio instance, and handles streaming responses.

### Model Routing
1. Extract `model` from request JSON body
2. Match against configured models in each instance
3. Use fallback instance if no match found
4. Return 400 error if neither matches

### OpenAI Compatibility
- `/v1/models` returns list of all configured models
- Error responses match OpenAI format
- Forward all standard OpenAI endpoints
