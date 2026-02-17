from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from api.config import InstanceConfig, ProxyConfig, load_config


class TestLoadValidConfig:
    def test_load_valid_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [
                        {"name": "inst-a", "base_url": "http://localhost:1234"},
                        {"name": "inst-b", "base_url": "http://localhost:5678"},
                    ],
                    "fallback_instance": "inst-a",
                    "model_cache_ttl_seconds": 60,
                    "request_timeout_seconds": 10,
                },
                f,
            )
            f.flush()
            try:
                config = load_config(f.name)
                assert len(config.instances) == 2
                assert config.instances[0].name == "inst-a"
                assert config.instances[0].base_url == "http://localhost:1234"
                assert config.instances[1].name == "inst-b"
                assert config.fallback_instance == "inst-a"
                assert config.model_cache_ttl_seconds == 60
                assert config.request_timeout_seconds == 10
            finally:
                os.unlink(f.name)

    def test_single_instance(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            try:
                config = load_config(f.name)
                assert len(config.instances) == 1
                assert config.instances[0].name == "inst-a"
            finally:
                os.unlink(f.name)

    def test_multiple_instances(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [
                        {"name": "inst-a", "base_url": "http://localhost:1234"},
                        {"name": "inst-b", "base_url": "http://localhost:5678"},
                        {"name": "inst-c", "base_url": "http://192.168.1.1:1234"},
                    ],
                    "fallback_instance": "inst-b",
                },
                f,
            )
            f.flush()
            try:
                config = load_config(f.name)
                assert len(config.instances) == 3
                names = [i.name for i in config.instances]
                assert names == ["inst-a", "inst-b", "inst-c"]
            finally:
                os.unlink(f.name)

    def test_default_values(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            try:
                config = load_config(f.name)
                assert config.model_cache_ttl_seconds == 30
                assert config.request_timeout_seconds == 5
            finally:
                os.unlink(f.name)

    def test_explicit_ttl_and_timeout(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                    "model_cache_ttl_seconds": 120,
                    "request_timeout_seconds": 30,
                },
                f,
            )
            f.flush()
            try:
                config = load_config(f.name)
                assert config.model_cache_ttl_seconds == 120
                assert config.request_timeout_seconds == 30
            finally:
                os.unlink(f.name)


class TestLoadInvalidConfig:
    def test_missing_file(self):
        with pytest.raises(SystemExit):
            load_config("/nonexistent/path/to/config.yaml")

    def test_missing_fallback_instance(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {"instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}]},
                f,
            )
            f.flush()
            try:
                with pytest.raises(SystemExit):
                    load_config(f.name)
            finally:
                os.unlink(f.name)

    def test_missing_instances(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"fallback_instance": "inst-a"}, f)
            f.flush()
            try:
                with pytest.raises(SystemExit):
                    load_config(f.name)
            finally:
                os.unlink(f.name)

    def test_empty_instances_list(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {"instances": [], "fallback_instance": "inst-a"},
                f,
            )
            f.flush()
            try:
                with pytest.raises(SystemExit):
                    load_config(f.name)
            finally:
                os.unlink(f.name)

    def test_invalid_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            try:
                with pytest.raises(yaml.YAMLError):
                    load_config(f.name)
            finally:
                os.unlink(f.name)

    def test_missing_instance_name(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            try:
                with pytest.raises(SystemExit):
                    load_config(f.name)
            finally:
                os.unlink(f.name)

    def test_missing_instance_url(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            try:
                with pytest.raises(SystemExit):
                    load_config(f.name)
            finally:
                os.unlink(f.name)


class TestProxyConfig:
    def test_proxy_config_dataclass(self):
        config = ProxyConfig(
            instances=[InstanceConfig(name="test", base_url="http://localhost:1234")],
            fallback_instance="test",
            model_cache_ttl_seconds=45,
            request_timeout_seconds=10,
        )
        assert config.instances[0].name == "test"
        assert config.fallback_instance == "test"
        assert config.model_cache_ttl_seconds == 45
        assert config.request_timeout_seconds == 10

    def test_instance_config_dataclass(self):
        inst = InstanceConfig(name="test-instance", base_url="http://192.168.1.1:8080")
        assert inst.name == "test-instance"
        assert inst.base_url == "http://192.168.1.1:8080"
