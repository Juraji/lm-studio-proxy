"""
Configuration loader for the LM Studio proxy.

The configuration is read from `config.yaml` in the project root. It defines a list of instances and an optional fallback instance.
"""

from __future__ import annotations

import logging

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class InstanceConfig(BaseModel):
    name: str = Field(min_length=1, description="Instance name for routing")
    base_url: str = Field(min_length=1, description="Base URL of the LM Studio instance")

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return v


class ProxyConfig(BaseModel):
    instances: list[InstanceConfig] = Field(min_length=1, description="List of LM Studio instances")
    fallback_instance: str = Field(min_length=1, description="Fallback instance name when model not found")
    model_cache_ttl_seconds: int = Field(default=30, ge=1, le=3600, description="Cache TTL for model discovery")
    request_timeout_seconds: int = Field(default=5, ge=1, le=120, description="Request timeout in seconds")


def load_config(config_path: str) -> ProxyConfig:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error(f"Configuration file '{config_path}' not found. Please provide a valid config file.")
        exit(1)

    try:
        return ProxyConfig.model_validate(data)
    except Exception as e:
        logger.error(f"Invalid configuration: {e}")
        exit(1)
