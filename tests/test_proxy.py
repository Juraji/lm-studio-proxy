from __future__ import annotations

import json
import httpx
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

from config import ProxyConfig, InstanceConfig
from proxy import create_app


class MockAsyncIterator:
    def __init__(self, data: list):
        self.data = data
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.data):
            raise StopAsyncIteration
        item = self.data[self.index]
        self.index += 1
        return item


def make_mock_iterator(data: list):
    def iter_func():
        return MockAsyncIterator(data)
    return iter_func


def create_app_with_models(config: ProxyConfig, models_data: dict, http_client: httpx.AsyncClient | None = None):
    app = create_app(config, http_client=http_client)
    
    model_cache = {}
    all_models = []
    for inst in config.instances:
        data = models_data.get(inst.name, {"data": []})
        for model in data.get("data", []):
            model_id = model.get("id")
            if model_id:
                model_cache[model_id] = inst
                model["instance"] = inst.name
        all_models.extend(data.get("data", []))
    
    app.state.model_cache = model_cache
    app.state.all_models = all_models
    
    return app


@pytest.fixture
def config() -> ProxyConfig:
    return ProxyConfig(
        instances=[
            InstanceConfig(name="inst-a", base_url="http://localhost:1234"),
            InstanceConfig(name="inst-b", base_url="http://localhost:5678"),
        ],
        fallback_instance="inst-a",
    )


@pytest.mark.asyncio
async def test_startup():
    config = ProxyConfig(instances=[InstanceConfig(name="test", base_url="http://localhost:1234")])
    app = create_app(config)
    assert app is not None
    assert app.title == "LM Studio Proxy"


@pytest.mark.asyncio
async def test_health_endpoint():
    config = ProxyConfig(instances=[InstanceConfig(name="test", base_url="http://localhost:1234")])
    app = create_app(config)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_models_endpoint(config):
    models_data = {
        "inst-a": {"data": [{"id": "model-a", "object": "model"}, {"id": "model-b", "object": "model"}]},
        "inst-b": {"data": [{"id": "model-c", "object": "model"}]},
    }
    app = create_app_with_models(config, models_data)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v0/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        model_ids = {m["id"] for m in data["data"]}
        assert model_ids == {"model-a", "model-b", "model-c"}


@pytest.mark.asyncio
async def test_get_model_endpoint(config):
    models_data = {
        "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        "inst-b": {"data": []},
    }
    app = create_app_with_models(config, models_data)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v0/models/model-a")
        assert response.status_code == 200
        assert response.json()["id"] == "model-a"


@pytest.mark.asyncio
async def test_get_model_not_found(config):
    models_data = {
        "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        "inst-b": {"data": []},
    }
    app = create_app_with_models(config, models_data)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v0/models/nonexistent")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_routing(config):
    models_data = {
        "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        "inst-b": {"data": [{"id": "model-c", "object": "model"}]},
    }
    
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.aread = AsyncMock(return_value=b'{"choices":[{"message":{"content":"hello"}}]}')
    mock_response.aiter_raw = make_mock_iterator([b'{"choices":[{"message":{"content":"hello"}}]}'])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app_with_models(config, models_data, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v0/chat/completions",
            json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
        )

        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args.kwargs
        assert "localhost:1234" in call_kwargs["url"]
        assert "/api/v0/chat/completions" in call_kwargs["url"]


@pytest.mark.asyncio
async def test_fallback_routing(config):
    models_data = {
        "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        "inst-b": {"data": [{"id": "model-c", "object": "model"}]},
    }
    
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.aread = AsyncMock(return_value=b'{"choices":[{"message":{"content":"fallback"}}]}')
    mock_response.aiter_raw = make_mock_iterator([b'{"choices":[{"message":{"content":"fallback"}}]}'])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app_with_models(config, models_data, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v0/chat/completions",
            json={"model": "unknown-model", "messages": [{"role": "user", "content": "hi"}]},
        )

        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args.kwargs
        assert "localhost:1234" in call_kwargs["url"]


@pytest.mark.asyncio
async def test_unknown_model_no_fallback():
    config = ProxyConfig(instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")])
    models_data = {"inst-a": {"data": [{"id": "model-a", "object": "model"}]}}
    app = create_app_with_models(config, models_data)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v0/chat/completions",
            json={"model": "unknown-model", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["message"]


@pytest.mark.asyncio
async def test_non_streaming_proxy(config):
    models_data = {
        "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        "inst-b": {"data": []},
    }
    
    response_data = {"id": "chatcmpl-123", "choices": [{"message": {"role": "assistant", "content": "Hello"}}]}
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.aread = AsyncMock(return_value=json.dumps(response_data).encode())
    mock_response.aiter_raw = make_mock_iterator([json.dumps(response_data).encode()])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app_with_models(config, models_data, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v0/chat/completions",
            json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}], "stream": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["message"]["content"] == "Hello"


@pytest.mark.asyncio
async def test_streaming_proxy(config):
    models_data = {
        "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        "inst-b": {"data": []},
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/event-stream"}
    mock_response.aiter_bytes = make_mock_iterator([
        b'{"choices":[{"delta":{"content":"Hello"}}]}\n',
        b'{"choices":[{"delta":{"content":" World"}}]}\n',
    ])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app_with_models(config, models_data, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v0/chat/completions",
            json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}], "stream": True},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"

        chunks = []
        async for chunk in response.aiter_bytes():
            chunks.append(chunk)
        
        combined = b"".join(chunks)
        assert b"Hello" in combined
        assert b"World" in combined


@pytest.mark.asyncio
async def test_error_handling():
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

    config = ProxyConfig(instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")])
    models_data = {"inst-a": {"data": [{"id": "model-a", "object": "model"}]}}
    app = create_app_with_models(config, models_data, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v0/chat/completions",
            json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 503
        data = response.json()
        assert "message" in data


@pytest.mark.asyncio
async def test_multiple_instances_routing(config):
    models_data = {
        "inst-a": {"data": [{"id": "model-a", "object": "model"}, {"id": "model-b", "object": "model"}]},
        "inst-b": {"data": [{"id": "model-c", "object": "model"}]},
    }
    
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.aread = AsyncMock(return_value=b'{"choices":[{"message":{"content":"c"}}]}')
    mock_response.aiter_raw = make_mock_iterator([b'{"choices":[{"message":{"content":"c"}}]}'])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app_with_models(config, models_data, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/v0/chat/completions",
            json={"model": "model-c", "messages": [{"role": "user", "content": "hi"}]},
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert "localhost:5678" in call_kwargs["url"]
