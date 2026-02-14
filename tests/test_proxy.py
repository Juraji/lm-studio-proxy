"""
Basic tests for the LM Studio proxy.
"""

import pytest
from fastapi.testclient import TestClient
from proxy import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
