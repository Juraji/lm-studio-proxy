from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from api.config import InstanceConfig, ProxyConfig
from tests.conftest import create_app_with_models, make_mock_iterator


class TestProxyApp:
    @pytest.mark.asyncio
    async def test_startup(self):
        from api.config import InstanceConfig
        from api.proxy import create_app

        config = ProxyConfig(
            instances=[InstanceConfig(name="test", base_url="http://localhost:1234")],
            fallback_instance="test",
        )
        app = create_app(config)
        assert app is not None
        assert app.title == "LM Studio Proxy"


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        from api.config import InstanceConfig
        from api.proxy import create_app

        config = ProxyConfig(
            instances=[InstanceConfig(name="test", base_url="http://localhost:1234")],
            fallback_instance="test",
        )
        app = create_app(config)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}


class TestModelsEndpoint:
    @pytest.mark.asyncio
    async def test_models_endpoint(self, config):
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
    async def test_get_model_endpoint(self, config):
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
    async def test_get_model_not_found(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
            "inst-b": {"data": []},
        }
        app = create_app_with_models(config, models_data)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v0/models/nonexistent")
            assert response.status_code == 404


class TestV1ModelsEndpoint:
    @pytest.mark.asyncio
    async def test_v1_models_endpoint(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}, {"id": "model-b", "object": "model"}]},
            "inst-b": {"data": [{"id": "model-c", "object": "model"}]},
        }
        app = create_app_with_models(config, models_data)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/models")
            assert response.status_code == 200
            data = response.json()
            assert "models" in data
            model_keys = {m["key"] for m in data["models"]}
            assert model_keys == {"model-a", "model-b", "model-c"}


class TestRouting:
    @pytest.mark.asyncio
    async def test_routing(self, config):
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
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
            )

            mock_client.send.assert_called_once()
            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "localhost:1234" in call_kwargs["url"]
            assert "/api/v0/chat/completions" in call_kwargs["url"]

    @pytest.mark.asyncio
    async def test_fallback_routing(self, config):
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
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={"model": "unknown-model", "messages": [{"role": "user", "content": "hi"}]},
            )

            mock_client.send.assert_called_once()
            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "localhost:1234" in call_kwargs["url"]

    @pytest.mark.asyncio
    async def test_multiple_instances_routing(self, config):
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
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-c", "messages": [{"role": "user", "content": "hi"}]},
            )

            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "localhost:5678" in call_kwargs["url"]

    @pytest.mark.asyncio
    async def test_v1_routing(self, config):
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
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v1/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
            )

            mock_client.send.assert_called_once()
            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "localhost:1234" in call_kwargs["url"]
            assert "/api/v1/chat/completions" in call_kwargs["url"]

    @pytest.mark.asyncio
    async def test_v1_fallback_routing(self, config):
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
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v1/chat/completions",
                json={"model": "unknown-model", "messages": [{"role": "user", "content": "hi"}]},
            )

            mock_client.send.assert_called_once()
            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "localhost:1234" in call_kwargs["url"]


class TestStreaming:
    @pytest.mark.asyncio
    async def test_non_streaming_proxy(self, config):
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
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

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
    async def test_streaming_proxy(self, config):
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
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

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


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_error_handling(self):
        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        from api.config import InstanceConfig

        config = ProxyConfig(
            instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")],
            fallback_instance="inst-a",
        )
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


class TestRequestTimeout:
    @pytest.mark.asyncio
    async def test_request_timeout(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert response.status_code == 502


class TestResponseForwarding:
    @pytest.mark.asyncio
    async def test_response_status_forwarded(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"id":"test"}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_response_headers_forwarded(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "application/json",
            "x-custom-header": "test-value",
        }
        mock_response.aread = AsyncMock(return_value=b'{"id":"test"}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert response.headers.get("x-custom-header") == "test-value"

    @pytest.mark.asyncio
    async def test_non_streaming_content_type(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[]}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}], "stream": False},
            )
            assert response.headers.get("content-type") == "application/json"

    @pytest.mark.asyncio
    async def test_streaming_content_type(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.aiter_bytes = make_mock_iterator([b'data: {"choices":[]}\n'])

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}], "stream": True},
            )
            assert response.headers.get("content-type") == "text/event-stream"


class TestFullRoundTrip:
    @pytest.mark.asyncio
    async def test_proxy_v0_chat_completion(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        response_data = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "model-a",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}
            ],
        }
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=json.dumps(response_data).encode())
        mock_response.aiter_raw = make_mock_iterator([json.dumps(response_data).encode()])

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "Hello"}]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["choices"][0]["message"]["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_proxy_v1_chat_completion(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        response_data = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "model-a",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "Response!"}, "finish_reason": "stop"}
            ],
        }
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=json.dumps(response_data).encode())
        mock_response.aiter_raw = make_mock_iterator([json.dumps(response_data).encode()])

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "Hello"}]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["choices"][0]["message"]["content"] == "Response!"


class TestHeaderForwarding:
    @pytest.mark.asyncio
    async def test_authorization_header_forwarded(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[]}')

        mock_client = AsyncMock()
        mock_request = MagicMock()
        mock_client.build_request = MagicMock(return_value=mock_request)
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
            )
            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["authorization"] == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_content_type_header_forwarded(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[]}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
            )
            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "content-type" in call_kwargs["headers"]


class TestDifferentMethods:
    @pytest.mark.asyncio
    async def test_proxy_post_method(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"result":"ok"}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}]},
            )
            call_kwargs = mock_client.build_request.call_args.kwargs
            assert call_kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_proxy_get_method_routing(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v0/models/model-a")
            assert response.status_code == 200


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_instances_with_fallback_only(self):

        config = ProxyConfig(
            instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")],
            fallback_instance="inst-a",
        )
        models_data = {"inst-a": {"data": []}}

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[{"message":{"content":"fallback"}}]}')
        mock_response.aiter_raw = make_mock_iterator([b'{"choices":[{"message":{"content":"fallback"}}]}'])

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v0/chat/completions",
                json={"model": "unknown-model", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_fallback_only_routing(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
            "inst-b": {"data": []},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[{"message":{"content":"fallback"}}]}')
        mock_response.aiter_raw = make_mock_iterator([b'{"choices":[{"message":{"content":"fallback"}}]}'])

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={"model": "unknown-model", "messages": [{"role": "user", "content": "hi"}]},
            )

            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "localhost:1234" in str(call_kwargs["url"])

    @pytest.mark.asyncio
    async def test_model_name_with_dashes(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-with-dashes", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[]}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-with-dashes", "messages": [{"role": "user", "content": "hi"}]},
            )

            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "localhost:1234" in str(call_kwargs["url"])

    @pytest.mark.asyncio
    async def test_large_request_body(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        large_content = "x" * 10000

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[]}')

        mock_client = AsyncMock()
        mock_request = MagicMock()
        mock_client.build_request = MagicMock(return_value=mock_request)
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={
                    "model": "model-a",
                    "messages": [{"role": "user", "content": large_content}],
                },
            )

            call_kwargs = mock_client.build_request.call_args.kwargs
            assert call_kwargs["content"] is not None
            assert len(call_kwargs["content"]) > 5000

    @pytest.mark.asyncio
    async def test_routing_to_specific_model(self, config):
        models_data = {
            "inst-a": {
                "data": [
                    {"id": "model-a", "object": "model"},
                    {"id": "model-b", "object": "model"},
                ]
            },
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[]}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-b", "messages": [{"role": "user", "content": "hi"}]},
            )

            call_kwargs = mock_client.build_request.call_args.kwargs
            assert "localhost:1234" in str(call_kwargs["url"])

    @pytest.mark.asyncio
    async def test_unknown_model_routes_to_fallback(self):

        config = ProxyConfig(
            instances=[
                InstanceConfig(name="inst-a", base_url="http://localhost:1234"),
                InstanceConfig(name="inst-b", base_url="http://localhost:5678"),
            ],
            fallback_instance="inst-a",
        )
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
            "inst-b": {"data": []},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[]}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v0/chat/completions",
                json={"model": "nonexistent-model", "messages": [{"role": "user", "content": "hi"}]},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_streaming_empty_chunks(self, config):
        models_data = {
            "inst-a": {"data": [{"id": "model-a", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.aiter_bytes = make_mock_iterator([b"", b'data: {}\n'])

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data, http_client=mock_client)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v0/chat/completions",
                json={"model": "model-a", "messages": [{"role": "user", "content": "hi"}], "stream": True},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_v0_and_v1_use_different_caches(self, config):
        models_data_v0 = {
            "inst-a": {"data": [{"id": "model-v0", "object": "model"}]},
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread = AsyncMock(return_value=b'{"choices":[]}')

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=MagicMock())
        mock_client.send = AsyncMock(return_value=mock_response)

        app = create_app_with_models(config, models_data_v0, http_client=mock_client)

        assert app.state.model_cache_v0 is not app.state.model_cache_v1
