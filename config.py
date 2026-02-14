"""
Configuration loader for the LM Studio proxy.

The configuration is read from `config.yaml` in the project root. It defines a list of instances and an optional fallback instance.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

import yaml

CONFIG_FILE = "config.yaml"

@dataclass
class InstanceConfig:
    name: str
    base_url: str
    models: List[str] = field(default_factory=list)

@dataclass
class ProxyConfig:
    instances: List[InstanceConfig]
    fallback_instance: Optional[str] = None


def load_config() -> ProxyConfig:
    """Load and parse the YAML configuration.

    Raises a ``FileNotFoundError`` if the config file does not exist.
    """
    path = os.path.join(os.getcwd(), CONFIG_FILE)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    instances_data = data.get("instances", [])
    instances: List[InstanceConfig] = []
    for inst in instances_data:
        instances.append(
            InstanceConfig(
                name=inst["name"],
                base_url=inst["base_url"],
                models=list(inst.get("models", [])),
            )
        )

    fallback = data.get("fallback_instance")
    return ProxyConfig(instances=instances, fallback_instance=fallback)
