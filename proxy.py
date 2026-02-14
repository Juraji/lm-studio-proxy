"""
FastAPI application that proxies OpenAI‑compatible requests to LM Studio instances.

The implementation is minimal and follows the checklist in `Plan.md`.
"""

from __future__ import annotations
from typing import Dict, Optional
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse, JSONResponse

# Load configuration once at startup
from config import load_config, InstanceConfig

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(_: FastAPI):
    global client
    # Startup - create HTTPX client
    client = httpx.AsyncClient()
    yield
    # Shutdown - close HTTPX client
    if client:
        await client.aclose()

app = FastAPI(title="LM Studio Proxy", lifespan=lifespan)

# Global HTTPX client to reuse connections across requests
client: httpx.AsyncClient | None = None

config = load_config()

@app.middleware("http")
async def add_headers(request: Request, call_next):
    # Placeholder for future request logging or header manipulation
    return await call_next(request)

# OpenAI‑style error handling
@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail}})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"message": str(exc)}})

@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception):
    # Log the exception if needed; for now just return 500
    return JSONResponse(status_code=500, content={"error": {"message": "Internal server error"}})

@app.get("/health")
async def health_check():
    return {"status": "ok"}

async def forward_request(
        request: Request,
        target_base_url: str,
    ) -> Response:
        """Forward the incoming FastAPI request to the selected LM Studio instance.

        The function now uses a global :class:`httpx.AsyncClient` that is created on startup and closed on shutdown. This ensures
        persistent connections and proper resource cleanup when the application stops.
        """
        # Build the full URL to forward to
        path = request.url.path.replace("/v1", "")  # strip the proxy prefix
        url = f"{target_base_url}{path}"

        # Prepare headers, preserving Authorization and Content-Type
        headers: Dict[str, str] = {
            key: value for key, value in request.headers.items() if key.lower() in {"authorization", "content-type"}
        }

        body = await request.body()
        assert client is not None, "HTTPX client not initialized"
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            timeout=None,  # allow long-running streams
        )

        return StreamingResponse(resp.aiter_raw(), status_code=resp.status_code, headers=dict(resp.headers))

@app.api_route("/v1/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_endpoint(request: Request):
    # Intercept /v1/models to return the list of available models
    if request.url.path == "/v1/models":
        # Gather all unique model IDs from configuration
        model_ids = {m for inst in config.instances for m in inst.models}
        data = [
            {
                "id": mid,
                "object": "model",
                "owned_by": "organisation_owner"
            } for mid in sorted(model_ids)
        ]
        return JSONResponse(status_code=200, content={"object": "list", "data": data})

    # Extract model name from JSON body if present
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    model_name = payload.get("model") if isinstance(payload, dict) else None

    # Determine target instance
    target: Optional[InstanceConfig] = None
    for inst in config.instances:
        if model_name and model_name in inst.models:
            target = inst
            break
    if not target and config.fallback_instance:
        target = next((i for i in config.instances if i.name == config.fallback_instance), None)

    if not target:
        raise HTTPException(status_code=400, detail=f"Model '{model_name}' not found and no fallback defined")

    return await forward_request(request, target.base_url)
