# AGENTS.md - LM Studio Proxy
FastAPI proxy forwarding requests to LM Studio's REST API v0 (`/api/v0/*`).

## Development Environment
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Note that any new dependency should be added to requirements.txt.
And then installed using `pip install -r requirements.txt` after activating the venv.

## Commands
### Running
```bash
./start.sh
# or: source .venv/bin/activate && python -m api.main
```

### Testing
```bash
pytest                           # all tests
pytest -v                        # verbose
pytest tests/test_proxy.py -v    # specific file
pytest tests/test_proxy.py::test_health_endpoint -v  # single test
pytest -k "test_model" -v       # pattern match
```

### Linting
```bash
ruff check .          # lint
ruff check --fix .    # auto-fix
```

## Code Style
### Imports (in order)
```python
from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import FastAPI

from api.config import ProxyConfig
```

### Naming
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `SCREAMING_SNAKE_CASE`
- Private methods: `_prefix`

### Type Hints
- Use Python 3.10+ syntax: `str | None` (not `Optional[str]`)
- Add hints to all params and returns
```python
async def forward_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    content: Any = None,
) -> httpx.Response:
```

### Formatting
- 4 spaces, max 100 chars, trailing commas
- One blank line between top-level definitions

### Dataclasses
```python
@dataclass
class InstanceConfig:
    name: str
    base_url: str
```

### Error Handling
```python
raise HTTPException(status_code=400, detail=f"Model '{model_name}' not found")
```
- Use `HTTPException` for HTTP errors
- Generic exceptions → 500 with safe message

### Async/Await
- Use `async def` for route handlers
- Use `httpx.AsyncClient`
- Manage lifecycle (startup/shutdown)
- Always await, never `.result()`

### Testing
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
- Use `pytest` + `pytest-asyncio`
- Mock external deps (`httpx.AsyncClient`, config)
- Use `@pytest.fixture`

## Project Structure
```
lm-studio-proxy/
├── api/
│   ├── __init__.py
│   ├── main.py     # uvicorn entry
│   ├── proxy.py    # FastAPI app + routing
│   └── config.py   # config loading
├── config.yaml # user config
├── requirements.txt
├── start.sh        # startup script (keep in root for visibility)
└── tests/
    └── test_proxy.py
```

## Key Patterns
- **Auto-Discovery**: Fetches models from LM Studio instances at startup, caches for routing
- **Model Routing**: Routes by `model` field, falls back to `fallback_instance`
- **Forwarding**: `forward_request()` handles regular + streaming responses

## Agents
- In planning mode, you are prohibited from making any changes to the code.
- Delegate code exploration and research tasks to the explore subagent.
- Delegate coding and testing to the general subagent
