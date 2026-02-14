import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
import httpx

# Dummy response class mimicking httpx.Response behavior
class DummyResponse:
    def __init__(self, status=200, content=b"{}", headers=None):
        self.status_code = status
        self._content = content
        self.headers = headers or {}

    async def aiter_raw(self):
        # Yield the entire content as one chunk for simplicity
        yield self._content

# Dummy client that returns a preset response; request method will be overridden by MagicMock if needed
class DummyClient:
    def __init__(self, response: DummyResponse | None = None):
        self.response = response

    async def request(self, *args, **kwargs):  # pragma: no cover - overridden in tests
        return self.response

# Mock configuration for tests
MOCK_CONFIG = {
    "instances": [
        {"name": "primary", "base_url": "http://primary/v1", "models": ["gpt-3.5-turbo"]},
        {"name": "fallback", "base_url": "http://fallback/v1", "models": ["text-davinci-003"]}
    ],
    "fallback_instance": "fallback"
}

# Helper to create a TestClient with patched config and httpx client

def _patched_client(response: DummyResponse):
    from types import SimpleNamespace
    class DummyInstance:
        def __init__(self, name, base_url, models):
            self.name = name
            self.base_url = base_url
            self.models = models
    mock_instances = [DummyInstance(**inst) for inst in MOCK_CONFIG['instances']]
    mock_config_obj = SimpleNamespace(instances=mock_instances, fallback_instance=MOCK_CONFIG.get('fallback_instance'))
    cfg_patch = patch('proxy.config', mock_config_obj)
    httpx_patch = patch.object(httpx, 'AsyncClient', lambda *_, **__: DummyClient(response))
    cfg_patch.start(); httpx_patch.start()
    import importlib
    proxy_module = importlib.reload(importlib.import_module('proxy'))
    test_client = TestClient(proxy_module.app)
    return test_client, cfg_patch, httpx_patch

# Test routing logic

def test_routing():
    resp_obj = DummyResponse(status=200, content=b"{}")
    client, cfg_p, httpx_p = _patched_client(resp_obj)
    r = client.post("/v1/chat/completions", json={"model": "gpt-3.5-turbo"})
    assert r.status_code == 200
    # Fallback route
    client2, cfg_p2, httpx_p2 = _patched_client(resp_obj)
    r2 = client2.post("/v1/chat/completions", json={"model": "unknown-model"})
    assert r2.status_code == 200
    cfg_p.stop(); httpx_p.stop(); cfg_p2.stop(); httpx_p2.stop()

# Test streaming support

def test_streaming():
    class StreamResp(DummyResponse):
        def __init__(self, data_chunks):
            super().__init__(status=200)
            self.data_chunks = data_chunks

        async def aiter_raw(self):
            for chunk in self.data_chunks:
                yield chunk
    stream_resp = StreamResp([b"data: chunk1\n", b"data: chunk2\n"])
    client, cfg_p, httpx_p = _patched_client(stream_resp)
    r = client.post("/v1/chat/completions", json={"model": "gpt-3.5-turbo"})
    assert r.status_code == 200
    data = r.content
    assert b"data: chunk1\n" in data and b"data: chunk2\n" in data
    cfg_p.stop(); httpx_p.stop()

# Test multiple API instances handling

def test_multiple_apis():
    primary_resp = DummyResponse(status=200, content=b'{"primary":true}')
    fallback_resp = DummyResponse(status=200, content=b'{"fallback":true}')

    def request_side_effect(*args, **kwargs):
        url = kwargs.get('url') or args[1]
        if "http://primary/v1/chat/completions" in str(url):
            return primary_resp
        elif "http://fallback/v1/chat/completions" in str(url):
            return fallback_resp
        raise ValueError(f"Unexpected URL: {url}")

    dummy_client = DummyClient()
    dummy_client.request = AsyncMock(side_effect=request_side_effect)
    from types import SimpleNamespace
    class DummyInstance:
        def __init__(self, name, base_url, models):
            self.name = name
            self.base_url = base_url
            self.models = models
    mock_instances = [DummyInstance(**inst) for inst in MOCK_CONFIG['instances']]
    mock_config_obj = SimpleNamespace(instances=mock_instances, fallback_instance=MOCK_CONFIG.get('fallback_instance'))
    cfg_patch = patch('proxy.config', mock_config_obj)
    httpx_patch = patch.object(httpx, 'AsyncClient', lambda *_, **__: dummy_client)
    cfg_patch.start(); httpx_patch.start()
    import importlib
    proxy_module = importlib.reload(importlib.import_module('proxy'))
    cfg_patch.stop()
    cfg_patch2 = patch.object(proxy_module, 'config', mock_config_obj)
    cfg_patch2.start()
    test_client = TestClient(proxy_module.app)
    r1 = test_client.post("/v1/chat/completions", json={"model": "gpt-3.5-turbo"})
    assert r1.status_code == 200 and b'primary' in r1.content
    r2 = test_client.post("/v1/chat/completions", json={"model": "text-davinci-003"})
    assert r2.status_code == 200 and b'fallback' in r2.content
    cfg_patch.stop(); httpx_patch.stop(); cfg_patch2.stop()
