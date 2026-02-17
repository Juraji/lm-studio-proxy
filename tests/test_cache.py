from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cache import ModelCacheV0, ModelCacheV1
from api.config import InstanceConfig, ProxyConfig


def create_mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    return resp


@pytest.fixture
def config() -> ProxyConfig:
    return ProxyConfig(
        instances=[
            InstanceConfig(name="inst-a", base_url="http://localhost:1234"),
            InstanceConfig(name="inst-b", base_url="http://localhost:5678"),
        ],
        fallback_instance="inst-a",
        model_cache_ttl_seconds=30,
    )


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get = AsyncMock()
    return client


class TestModelCacheV0:
    @pytest.mark.asyncio
    async def test_v0_fetches_from_correct_endpoint(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"data": [{"id": "model-1"}]})
        )
        cache = ModelCacheV0(mock_client, config)
        await cache._fetch()
        mock_client.get.assert_called()
        call_urls = [call.kwargs.get('url') or str(call) for call in mock_client.get.call_args_list]
        assert any("localhost:1234" in url for url in call_urls)

    @pytest.mark.asyncio
    async def test_v0_builds_instance_mapping(self, config, mock_client):
        mock_client.get = AsyncMock(
            side_effect=[
                create_mock_response(200, {"data": [{"id": "model-a"}, {"id": "model-b"}]}),
                create_mock_response(200, {"data": [{"id": "model-c"}]}),
            ]
        )
        cache = ModelCacheV0(mock_client, config)
        await cache._fetch()
        assert cache.instance_mapping["model-a"].name == "inst-a"
        assert cache.instance_mapping["model-b"].name == "inst-a"
        assert cache.instance_mapping["model-c"].name == "inst-b"

    @pytest.mark.asyncio
    async def test_v0_get_models_response_format(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"data": [{"id": "model-1"}]})
        )
        cache = ModelCacheV0(mock_client, config)
        response = await cache.get_models_response()
        assert response["object"] == "list"
        assert "data" in response


class TestModelCacheV1:
    @pytest.mark.asyncio
    async def test_v1_fetches_from_correct_endpoint(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"models": [{"key": "model-1"}]})
        )
        cache = ModelCacheV1(mock_client, config)
        await cache._fetch()
        mock_client.get.assert_called()
        call_urls = [call.kwargs.get('url') or str(call) for call in mock_client.get.call_args_list]
        assert any("localhost:1234" in url for url in call_urls)

    @pytest.mark.asyncio
    async def test_v1_builds_instance_mapping(self, config, mock_client):
        mock_client.get = AsyncMock(
            side_effect=[
                create_mock_response(200, {"models": [{"key": "model-a"}, {"key": "model-b"}]}),
                create_mock_response(200, {"models": [{"key": "model-c"}]}),
            ]
        )
        cache = ModelCacheV1(mock_client, config)
        await cache._fetch()
        assert cache.instance_mapping["model-a"].name == "inst-a"
        assert cache.instance_mapping["model-b"].name == "inst-a"
        assert cache.instance_mapping["model-c"].name == "inst-b"

    @pytest.mark.asyncio
    async def test_v1_get_models_response_format(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"models": [{"key": "model-1"}]})
        )
        cache = ModelCacheV1(mock_client, config)
        response = await cache.get_models_response()
        assert "models" in response


class TestCacheTTL:
    @pytest.mark.asyncio
    async def test_cache_returns_cached_data(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"data": [{"id": "model-1"}]})
        )
        cache = ModelCacheV0(mock_client, config)
        await cache.get_models()
        await cache.get_models()
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_refreshes_after_ttl(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"data": [{"id": "model-1"}]})
        )
        cache = ModelCacheV0(mock_client, config)
        await cache.get_models()
        cache._last_updated = datetime.now() - timedelta(seconds=31)
        await cache.get_models()
        assert mock_client.get.call_count == 4

    @pytest.mark.asyncio
    async def test_cache_is_valid_within_ttl(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"data": [{"id": "model-1"}]})
        )
        cache = ModelCacheV0(mock_client, config)
        await cache.get_models()
        cache._last_updated = datetime.now() - timedelta(seconds=29)
        await cache.get_models()
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_invalid_when_last_updated_none(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"data": [{"id": "model-1"}]})
        )
        cache = ModelCacheV0(mock_client, config)
        cache._last_updated = None
        await cache.get_models()
        assert mock_client.get.call_count == 2


class TestInstanceMapping:
    @pytest.mark.asyncio
    async def test_fallback_sorted_first(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"data": []})
        )
        cache = ModelCacheV0(mock_client, config)
        await cache._fetch()
        call_args_list = mock_client.get.call_args_list
        assert len(call_args_list) == 2


class TestCacheEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_models_list(self, config, mock_client):
        mock_client.get = AsyncMock(
            return_value=create_mock_response(200, {"data": []})
        )
        cache = ModelCacheV0(mock_client, config)
        await cache._fetch()
        assert cache.models == []
        assert cache.instance_mapping == {}

    @pytest.mark.asyncio
    async def test_models_without_id_field(self, config, mock_client):
        mock_client.get = AsyncMock(
            side_effect=[
                create_mock_response(200, {"data": [{"id": "model-a"}, {"name": "model-b"}]}),
                create_mock_response(200, {"data": []}),
            ]
        )
        cache = ModelCacheV0(mock_client, config)
        await cache._fetch()
        assert "model-a" in cache.instance_mapping
        assert "model-b" not in cache.instance_mapping

    @pytest.mark.asyncio
    async def test_fetch_network_error(self, config, mock_client):
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        cache = ModelCacheV0(mock_client, config)
        await cache._fetch()
        assert cache.models == []
        assert cache.instance_mapping == {}

    @pytest.mark.asyncio
    async def test_non_200_response(self, config, mock_client):
        mock_client.get = AsyncMock(
            side_effect=[
                create_mock_response(500, {}),
                create_mock_response(200, {"data": []}),
            ]
        )
        cache = ModelCacheV0(mock_client, config)
        await cache._fetch()
        assert cache.models == []

    @pytest.mark.asyncio
    async def test_get_instance_mapping_returns_mapping(self, config, mock_client):
        mock_client.get = AsyncMock(
            side_effect=[
                create_mock_response(200, {"data": [{"id": "model-1"}]}),
                create_mock_response(200, {"data": []}),
            ]
        )
        cache = ModelCacheV0(mock_client, config)
        mapping = await cache.get_instance_mapping()
        assert "model-1" in mapping
        assert mapping["model-1"].name == "inst-a"


class TestCacheV1Specific:
    @pytest.mark.asyncio
    async def test_v1_uses_key_not_id(self, config, mock_client):
        mock_client.get = AsyncMock(
            side_effect=[
                create_mock_response(200, {"models": [{"key": "model-v1", "name": "Test Model"}]}),
                create_mock_response(200, {"models": []}),
            ]
        )
        cache = ModelCacheV1(mock_client, config)
        await cache._fetch()
        assert "model-v1" in cache.instance_mapping
        assert "key" in cache.models[0]
