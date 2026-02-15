"""
Configuration loader for the LM Studio proxy.

The configuration is read from `config.yaml` in the project root. It defines a list of instances and an optional fallback instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import yaml


@dataclass
class InstanceConfig:
    name: str
    base_url: str

@dataclass
class ProxyConfig:
    instances: List[InstanceConfig]
    fallback_instance: Optional[str] = None


def load_config(config_path: str) -> ProxyConfig:
    # Load the configuration file
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        import sys
        print(f"Configuration file '{config_path}' not found. Please provide a valid config file.")
        sys.exit(1)

    instances_data = data.get("instances", [])
    instances: List[InstanceConfig] = []
    for inst in instances_data:
        instances.append(
            InstanceConfig(
                name=inst["name"],
                base_url=inst["base_url"],
            )
        )

    fallback = data.get("fallback_instance")
    return ProxyConfig(instances=instances, fallback_instance=fallback)
