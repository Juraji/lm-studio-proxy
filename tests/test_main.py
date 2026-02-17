from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

from api.config import InstanceConfig, ProxyConfig


class TestCLIDefaults:
    @pytest.mark.asyncio
    async def test_cli_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            config_path = f.name

        try:
            with patch("sys.argv", ["main.py"]):
                from api.main import main
                with patch("api.main.load_config") as mock_load, patch(
                    "api.main.create_app"
                ) as mock_create, patch("api.main.uvicorn") as mock_uvicorn:
                    mock_load.return_value = ProxyConfig(
                        instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")],
                        fallback_instance="inst-a",
                    )
                    mock_create.return_value = MagicMock()

                    main()

                    mock_uvicorn.run.assert_called_once()
                    call_kwargs = mock_uvicorn.run.call_args.kwargs
                    assert call_kwargs["host"] == "0.0.0.0"
                    assert call_kwargs["port"] == 8000
        finally:
            os.unlink(config_path)

    @pytest.mark.asyncio
    async def test_cli_custom_config_path(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            config_path = f.name

        try:
            with patch("sys.argv", ["main.py", "--config", config_path]):
                from api.main import main
                with patch("api.main.load_config") as mock_load, patch(
                    "api.main.create_app"
                ) as mock_create, patch("api.main.uvicorn") as _:
                    mock_load.return_value = ProxyConfig(
                        instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")],
                        fallback_instance="inst-a",
                    )
                    mock_create.return_value = MagicMock()

                    main()

                    mock_load.assert_called_once_with(config_path)
        finally:
            os.unlink(config_path)

    @pytest.mark.asyncio
    async def test_cli_custom_host(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            config_path = f.name

        try:
            with patch("sys.argv", ["main.py", "--host", "127.0.0.1"]):
                from api.main import main
                with patch("api.main.load_config") as mock_load, patch(
                    "api.main.create_app"
                ) as mock_create, patch("api.main.uvicorn") as mock_uvicorn:
                    mock_load.return_value = ProxyConfig(
                        instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")],
                        fallback_instance="inst-a",
                    )
                    mock_create.return_value = MagicMock()

                    main()

                    call_kwargs = mock_uvicorn.run.call_args.kwargs
                    assert call_kwargs["host"] == "127.0.0.1"
        finally:
            os.unlink(config_path)

    @pytest.mark.asyncio
    async def test_cli_custom_port(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            config_path = f.name

        try:
            with patch("sys.argv", ["main.py", "--port", "9000"]):
                from api.main import main
                with patch("api.main.load_config") as mock_load, patch(
                    "api.main.create_app"
                ) as mock_create, patch("api.main.uvicorn") as mock_uvicorn:
                    mock_load.return_value = ProxyConfig(
                        instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")],
                        fallback_instance="inst-a",
                    )
                    mock_create.return_value = MagicMock()

                    main()

                    call_kwargs = mock_uvicorn.run.call_args.kwargs
                    assert call_kwargs["port"] == 9000
        finally:
            os.unlink(config_path)

    @pytest.mark.asyncio
    async def test_cli_debug_flag(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            config_path = f.name

        try:
            with patch("sys.argv", ["main.py", "--debug"]):
                from api.main import main
                with patch("api.main.load_config") as mock_load, patch(
                    "api.main.create_app"
                ) as mock_create, patch("api.main.uvicorn") as _:
                    mock_load.return_value = ProxyConfig(
                        instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")],
                        fallback_instance="inst-a",
                    )
                    mock_create.return_value = MagicMock()

                    import logging
                    with patch("api.main.logging.root.setLevel") as mock_set_level:
                        main()
                        mock_set_level.assert_called_once_with(logging.DEBUG)
        finally:
            os.unlink(config_path)

    @pytest.mark.asyncio
    async def test_cli_missing_config(self):
        with patch("sys.argv", ["main.py", "--config", "/nonexistent/config.yaml"]):
            from api.main import main
            with patch("api.main.load_config", side_effect=SystemExit(1)):
                with pytest.raises(SystemExit):
                    main()


class TestCLIArguments:
    @pytest.mark.asyncio
    async def test_cli_short_flags(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            config_path = f.name

        try:
            with patch(
                "sys.argv", ["main.py", "-c", config_path, "-H", "localhost", "-p", "3000", "-d"]
            ):
                from api.main import main
                with patch("api.main.load_config") as mock_load, patch(
                    "api.main.create_app"
                ) as mock_create, patch("api.main.uvicorn") as mock_uvicorn:
                    mock_load.return_value = ProxyConfig(
                        instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")],
                        fallback_instance="inst-a",
                    )
                    mock_create.return_value = MagicMock()

                    main()

                    call_kwargs = mock_uvicorn.run.call_args.kwargs
                    assert call_kwargs["host"] == "localhost"
                    assert call_kwargs["port"] == 3000
        finally:
            os.unlink(config_path)


class TestUvicornIntegration:
    @pytest.mark.asyncio
    async def test_uvicorn_called_with_app(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "instances": [{"name": "inst-a", "base_url": "http://localhost:1234"}],
                    "fallback_instance": "inst-a",
                },
                f,
            )
            f.flush()
            config_path = f.name

        try:
            with patch("sys.argv", ["main.py"]):
                from api.main import main
                with patch("api.main.load_config") as mock_load, patch(
                    "api.main.create_app"
                ) as mock_create, patch("api.main.uvicorn") as mock_uvicorn:
                    mock_app = MagicMock()
                    mock_create.return_value = mock_app
                    mock_load.return_value = ProxyConfig(
                        instances=[InstanceConfig(name="inst-a", base_url="http://localhost:1234")],
                        fallback_instance="inst-a",
                    )

                    main()

                    mock_uvicorn.run.assert_called_once()
                    call_args = mock_uvicorn.run.call_args
                    assert call_args[0][0] is mock_app
        finally:
            os.unlink(config_path)
