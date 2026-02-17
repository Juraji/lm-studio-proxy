from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.config import InstanceConfig, ProxyConfig
from api.proxy import create_app
from api.cache import ModelCacheV0, ModelCacheV1


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


@pytest.fixture
def config() -> ProxyConfig:
    return ProxyConfig(
        instances=[
            InstanceConfig(name="inst-a", base_url="http://localhost:1234"),
            InstanceConfig(name="inst-b", base_url="http://localhost:5678"),
        ],
        fallback_instance="inst-a",
    )


def create_app_with_models(config: ProxyConfig, models_data: dict, http_client: MagicMock | None = None):
    app = create_app(config)

    if http_client is None:
        http_client = AsyncMock()
    app.state.http_client = http_client

    model_cache_v0 = ModelCacheV0(http_client, config)
    model_cache_v1 = ModelCacheV1(http_client, config)

    for inst in config.instances:
        data = models_data.get(inst.name, {"data": []})
        for model in data.get("data", []):
            model_id = model.get("id")
            if model_id:
                model_cache_v0.instance_mapping[model_id] = inst
                model_cache_v0.models.append(model)

                model_copy = model.copy()
                if "id" in model_copy:
                    model_copy["key"] = model_copy.pop("id")
                model_cache_v1.instance_mapping[model_id] = inst
                model_cache_v1.models.append(model_copy)

    from datetime import datetime
    model_cache_v0._last_updated = datetime.now()
    model_cache_v1._last_updated = datetime.now()

    app.state.model_cache_v0 = model_cache_v0
    app.state.model_cache_v1 = model_cache_v1

    return app
