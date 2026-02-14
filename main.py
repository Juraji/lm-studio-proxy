"""
Main entry point for the LM Studio proxy.

This file is intentionally minimal; it simply starts the FastAPI application defined in `proxy.py`.
"""

import argparse
import logging
import uvicorn
import uvicorn.logging

from config import load_config
from proxy import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="LM Studio Proxy")
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to the configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--host", "-H",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Setup logging
    handler = logging.StreamHandler()
    handler.setFormatter(uvicorn.logging.DefaultFormatter("%(levelprefix)s%(message)s"))
    logging.root.addHandler(handler)
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.root.setLevel(log_level)

    # Load app config and run
    config = load_config(args.config)
    app = create_app(config)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
