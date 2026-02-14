"""
Main entry point for the LM Studio proxy.

This file is intentionally minimal; it simply starts the FastAPI application defined in `proxy.py`.
"""

from config import load_config
from proxy import create_app

config = load_config()
app = create_app(config)

if __name__ == "__main__":
    from uvicorn import run
    run("main:app", host="0.0.0.0", port=8000, reload=True)
