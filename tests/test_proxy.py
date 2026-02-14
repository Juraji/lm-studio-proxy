from __future__ import annotations

import json
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from config import ProxyConfig, InstanceConfig
from proxy import create_app


@pytest.fixture
def config() -> ProxyConfig:
    return ProxyConfig(
        instances=[
            InstanceConfig(name="inst-a", base_url="http://localhost:1234/v1", models=["model-a", "model-b"]),
            InstanceConfig(name="inst-b", base_url="http://localhost:5678/v1", models=["model-c"]),
        ],
        fallback_instance="inst-a",
    )


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


@pytest.mark.asyncio
async def test_startup():
    config = ProxyConfig(instances=[InstanceConfig(name="test", base_url="http://localhost:1234/v1", models=[])])
    app = create_app(config)
    assert app is not None
    assert app.title == "LM Studio Proxy"


@pytest.mark.asyncio
async def test_health_endpoint():
    config = ProxyConfig(instances=[InstanceConfig(name="test", base_url="http://localhost:1234/v1", models=[])])
    app = create_app(config)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_models_endpoint(config):
    app = create_app(config)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        model_ids = {m["id"] for m in data["data"]}
        assert model_ids == {"model-a", "model-b", "model-c"}


@pytest.mark.asyncio
async def test_routing(config):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.aiter_raw = make_mock_iterator([b'{"choices":[{"message":{"content":"hello"}}]}'])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app(config, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/chat/completions",
            json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
        )

        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args.kwargs
        assert "localhost:1234" in call_kwargs["url"]
        assert "chat/completions" in call_kwargs["url"]


@pytest.mark.asyncio
async def test_fallback_routing(config):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.aiter_raw = make_mock_iterator([b'{"choices":[{"message":{"content":"fallback"}}]}'])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app(config, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/chat/completions",
            json={"model": "unknown-model", "messages": [{"role": "user", "content": "hi"}]},
        )

        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args.kwargs
        assert "localhost:1234" in call_kwargs["url"]


@pytest.mark.asyncio
async def test_unknown_model_no_fallback():
    config = ProxyConfig(instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234/v1", models=["model-a"])])
    app = create_app(config)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/chat/completions",
            json={"model": "unknown-model", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_non_streaming_proxy(config):
    response_data = {"id": "chatcmpl-123", "choices": [{"message": {"role": "assistant", "content": "Hello"}}]}
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.aiter_raw = make_mock_iterator([json.dumps(response_data).encode()])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app(config, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/chat/completions",
            json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}], "stream": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["message"]["content"] == "Hello"


@pytest.mark.asyncio
async def test_streaming_proxy(config):
    async def mock_stream():
        yield b'{"choices":[{"delta":{"content":"Hello"}}]}\n'
        yield b'{"choices":[{"delta":{"content":" World"}}]}\n'

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/event-stream"}
    mock_response.aiter_raw = lambda: mock_stream()

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app(config, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/chat/completions",
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
async def test_error_handling_openai_format():
    config = ProxyConfig(instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234/v1", models=["model-a"])])
    app = create_app(config)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/chat/completions",
            json={"model": "nonexistent", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "message" in data["error"]


@pytest.mark.asyncio
async def test_multiple_instances_routing(config):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.aiter_raw = make_mock_iterator([b'{"choices":[{"message":{"content":"c"}}]}'])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app(config, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/v1/chat/completions",
            json={"model": "model-c", "messages": [{"role": "user", "content": "hi"}]},
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert "localhost:5678" in call_kwargs["url"]


@pytest.mark.asyncio
async def test_config_without_models_uses_fallback():
    config = ProxyConfig(
        instances=[
            InstanceConfig(name="inst-a", base_url="http://localhost:1234/v1", models=[]),
        ],
        fallback_instance="inst-a",
    )

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.aiter_raw = make_mock_iterator([b'{"choices":[{"message":{"content":"ok"}}]}'])

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    app = create_app(config, http_client=mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/v1/chat/completions",
            json={"model": "any-model", "messages": [{"role": "user", "content": "hi"}]},
        )

        assert response.status_code == 200
