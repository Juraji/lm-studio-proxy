"""
FastAPI application that proxies OpenAI‑compatible requests to LM Studio instances.

The implementation is minimal and follows the checklist in `Plan.md`.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse

# Load configuration once at startup
from config import load_config, InstanceConfig

app = FastAPI(title="LM Studio Proxy")

config = load_config()

@app.middleware("http")
async def add_headers(request: Request, call_next):
    # Simple middleware to log requests (placeholder)
    return await call_next(request)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

async def forward_request(
    request: Request,
    target_base_url: str,
) -> Response:
    # Build the full URL to forward to
    path = request.url.path.replace("/v1", "")  # strip the proxy prefix
    url = f"{target_base_url}{path}"

    # Prepare headers, preserving Authorization and Content-Type
    headers: Dict[str, str] = {
        key: value for key, value in request.headers.items() if key.lower() in {"authorization", "content-type"}
    }

    body = await request.body()
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            timeout=None,  # allow long-running streams
            stream=True,
        )

    return StreamingResponse(resp.aiter_raw(), status_code=resp.status_code, headers=dict(resp.headers))

@app.api_route("/v1/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_endpoint(request: Request, full_path: str):
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
