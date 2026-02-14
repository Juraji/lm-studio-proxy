"""
Basic tests for the LM Studio proxy.
"""

import pytest
from fastapi.testclient import TestClient
from proxy import app, config

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models_list():
    # GET /v1/models should return the list of models from config without proxying.
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    # Ensure data is a list and contains all unique models from config.yaml
    expected_ids = sorted({m for inst in config.instances for m in inst.models})
    returned_ids = sorted([item["id"] for item in data["data"]])
    assert returned_ids == expected_ids
    # Each model should have object 'model' and owned_by 'organisation_owner'
    for item in data["data"]:
        assert item["object"] == "model"
        assert item["owned_by"] == "organisation_owner"
