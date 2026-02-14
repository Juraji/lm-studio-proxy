"""
Configuration loader for the LM Studio proxy.

The configuration is read from `config.yaml` in the project root. It defines a list of instances and an optional fallback instance.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import yaml

CONFIG_FILE = "config.yaml"

@dataclass
class InstanceConfig:
    name: str
    base_url: str

@dataclass
class ProxyConfig:
    instances: List[InstanceConfig]
    fallback_instance: Optional[str] = None


def load_config(config_path: str | None = None) -> ProxyConfig:
    """
    Loads configuration from a YAML file and creates a ProxyConfig object.

    :param config_path: Path to the configuration file; if ``None`` defaults
        to :data:`CONFIG_FILE` in the current working directory.
    :return: ProxyConfig instance that holds loaded instances and an optional
        fallback_instance.
    :raises FileNotFoundError: If the configuration file does not exist.
    :raises yaml.YAMLError: If YAML parsing fails.
    """

    # Resolve configuration file path
    if config_path is None:
        config_path = os.path.join(os.getcwd(), CONFIG_FILE)
        # If the default config does not exist, create a minimal one
        if not os.path.exists(config_path):
            import sys
            default_data = {
                "instances": [
                    {"name": "lms", "base_url": "http://localhost:1234"}
                ],
                # No fallback instance by default
                "fallback_instance": None,
            }
            try:
                with open(config_path, "w", encoding="utf-8") as f_write:
                    yaml.safe_dump(default_data, f_write)
                print(f"Created default configuration file at {config_path}. Please review and adjust as needed.")
            except Exception as e:
                print(f"Failed to create default config: {e}")

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
