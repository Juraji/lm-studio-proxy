"""
Main entry point for the LM Studio proxy.

This file is intentionally minimal; it simply starts the FastAPI application defined in `proxy.py`.
"""

from uvicorn import run

if __name__ == "__main__":
    # The host/port can be overridden via environment variables if needed.
    run("proxy:app", host="0.0.0.0", port=8000, reload=True)
