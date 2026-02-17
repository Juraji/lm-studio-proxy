"""
Model cache implementations for LM Studio proxy.

Provides version-specific caches (v0, v1) that handle:
- Fetching models from instances
- Caching with TTL-based eviction
- Instance routing mapping
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from api.config import InstanceConfig, ProxyConfig

logger = logging.getLogger(__name__)


class ModelCache(ABC):
    """Abstract base class for model caches."""

    def __init__(self, http_client: httpx.AsyncClient, config: ProxyConfig):
        self._http_client = http_client
        self._config = config
        self.models: list[dict[str, Any]] = []
        self.instance_mapping: dict[str, InstanceConfig] = {}
        self._last_updated: datetime | None = None
        self._fetch_lock = asyncio.Lock()

    def _is_valid(self) -> bool:
        """Check if cache is still valid based on TTL."""
        if self._last_updated is None:
            return False
        return datetime.now() < self._last_updated + timedelta(
            seconds=self._config.model_cache_ttl_seconds
        )

    async def get_models(self) -> list[dict[str, Any]]:
        """Get models list, refreshing cache if stale."""
        async with self._fetch_lock:
            if not self._is_valid():
                await self._fetch()
        return self.models

    async def get_instance_mapping(self) -> dict[str, InstanceConfig]:
        """Get model -> instance mapping, refreshing cache if stale."""
        async with self._fetch_lock:
            if not self._is_valid():
                await self._fetch()
        return self.instance_mapping

    async def get_instance_for_model(self, model_name: str) -> Optional[InstanceConfig]:
        instance_mapping = await self.get_instance_mapping()
        if model_name in instance_mapping:
            return instance_mapping[model_name]
        else:
            return None

    @abstractmethod
    async def _fetch(self) -> None:
        """Fetch models from instances and populate models + instance_mapping."""
        pass

    @abstractmethod
    async def get_models_response(self) -> dict[str, Any]:
        """Return the full API response format (v0 or v1)."""
        pass


class ModelCacheV0(ModelCache):
    """Cache for /api/v0/models format."""

    async def _fetch(self) -> None:
        """Fetch models from instances via v0 API."""
        self.models = []
        self.instance_mapping = {}

        # Sort instances with fallback first
        instances = sorted(
            self._config.instances,
            key=lambda i: 0 if i.name == self._config.fallback_instance else 1,
        )

        for inst in instances:
            try:
                resp = await self._http_client.get(
                    f"{inst.base_url}/api/v0/models",
                    timeout=self._config.request_timeout_seconds,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for model in data.get("data", []):
                        model_id = model.get("id")
                        if model_id:
                            self.instance_mapping[model_id] = inst
                    self.models.extend(data.get("data", []))
                logger.info(f"Discovered {len(self.models)} models from {inst.name}")
            except Exception as e:
                logger.warning(f"Failed to fetch v0 models from {inst.name}: {e}")

        self._last_updated = datetime.now()

    async def get_models_response(self) -> dict[str, Any]:
        """Return v0 API response format."""
        models = await self.get_models()
        return {"object": "list", "data": models}


class ModelCacheV1(ModelCache):
    """Cache for /api/v1/models format."""

    async def _fetch(self) -> None:
        """Fetch models from instances via v1 API."""
        self.models = []
        self.instance_mapping = {}

        # Sort instances with fallback first
        instances = sorted(
            self._config.instances,
            key=lambda i: 0 if i.name == self._config.fallback_instance else 1,
        )

        for inst in instances:
            try:
                resp = await self._http_client.get(
                    f"{inst.base_url}/api/v1/models",
                    timeout=self._config.request_timeout_seconds,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for model in data.get("models", []):
                        model_id = model.get("key")
                        if model_id:
                            self.instance_mapping[model_id] = inst
                    self.models.extend(data.get("models", []))
                logger.info(f"Discovered {len(self.models)} models from {inst.name}")
            except Exception as e:
                logger.warning(f"Failed to fetch v1 models from {inst.name}: {e}")

        self._last_updated = datetime.now()

    async def get_models_response(self) -> dict[str, Any]:
        """Return v1 API response format."""
        models = await self.get_models()
        return {"models": models}
