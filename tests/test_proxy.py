"""Test suite for the LM Studio proxy.

The tests cover:
1. Health‑check endpoint.
2. Models listing.
3. FastAPI lifespan client creation and cleanup.
"""

import httpx
from fastapi.testclient import TestClient

import proxy
# Import app, config, and the global proxy module to access its ``client`` variable.
from proxy import app, config

# Synchronous tests using FastAPI's TestClient.
client = TestClient(app)

def test_health() -> None:
    """Health endpoint returns 200 with JSON body."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_models_list() -> None:
    """Models endpoint returns list of model IDs from config."""
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    ids_in_response = {item["id"] for item in data["data"]}
    expected_ids = {m for inst in config.instances for m in inst.models}
    assert ids_in_response == expected_ids
    for item in data["data"]:
        assert {"id", "object", "owned_by"}.issubset(item.keys())

# Lifespan tests: verify client creation and cleanup.

def test_startup_initializes_client() -> None:
    """FastAPI startup creates a global httpx.AsyncClient instance."""
    class _MockAsyncClient:
        def __init__(self):
            self.aclose_called = False

        async def aclose(self) -> None:  # pragma: no cover - trivial helper
            self.aclose_called = True

    original_factory = httpx.AsyncClient
    try:
        httpx.AsyncClient = lambda *_, **__: _MockAsyncClient()
        with TestClient(app):
            pass
        assert proxy.client is not None
        assert isinstance(proxy.client, _MockAsyncClient)
    finally:
        httpx.AsyncClient = original_factory

def test_shutdown_closes_client() -> None:
    """FastAPI shutdown closes the global httpx.AsyncClient instance."""
    class _MockAsyncClient:
        def __init__(self):
            self.aclose_called = False

        async def aclose(self) -> None:  # pragma: no cover - trivial helper
            self.aclose_called = True

    original_factory = httpx.AsyncClient
    try:
        httpx.AsyncClient = lambda *_, **__: _MockAsyncClient()
        with TestClient(app):
            pass
        assert getattr(proxy.client, "aclose_called", False) is True
    finally:
        httpx.AsyncClient = original_factory
