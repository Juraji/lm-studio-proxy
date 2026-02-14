"""
Main entry point for the LM Studio proxy.

This file is intentionally minimal; it simply starts the FastAPI application defined in `proxy.py`.
"""

import argparse

from config import load_config
from proxy import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="LM Studio Proxy")
    parser.add_argument(
        "--config",
        "-c",
        default="config.yaml",
        help="Path to the configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    app = create_app(config)

    from uvicorn import run
    run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
