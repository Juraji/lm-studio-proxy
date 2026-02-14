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

from config import ProxyConfig, InstanceConfig

from contextlib import asynccontextmanager


def create_app(config: ProxyConfig, http_client: httpx.AsyncClient | None = None) -> FastAPI:
    client_owns_http_client = http_client is None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        nonlocal http_client
        if http_client is None:
            http_client = httpx.AsyncClient()
        yield
        if client_owns_http_client and http_client:
            await http_client.aclose()

    app = FastAPI(title="LM Studio Proxy", lifespan=lifespan)

    @app.middleware("http")
    async def add_headers(request: Request, call_next):
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail}})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"message": str(exc)}})

    @app.exception_handler(Exception)
    async def generic_exception_handler(_: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"error": {"message": "Internal server error"}})

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    async def forward_request(
            request: Request,
            target_base_url: str,
        ) -> Response:
        nonlocal http_client
        path = request.url.path.replace("/v1", "")
        url = f"{target_base_url}{path}"

        headers: Dict[str, str] = {
            key: value for key, value in request.headers.items() if key.lower() in {"authorization", "content-type"}
        }

        body = await request.body()

        if http_client is None:
            http_client = httpx.AsyncClient()
        resp = await http_client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            timeout=None,
        )
        return StreamingResponse(resp.aiter_raw(), status_code=resp.status_code, headers=dict(resp.headers))

    @app.api_route("/v1/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_endpoint(request: Request):
        if request.url.path == "/v1/models":
            model_ids = {m for inst in config.instances for m in inst.models}
            data = [
                {
                    "id": mid,
                    "object": "model",
                    "owned_by": "organisation_owner"
                } for mid in sorted(model_ids)
            ]
            return JSONResponse(status_code=200, content={"object": "list", "data": data})

        try:
            payload = await request.json()
        except Exception:
            payload = {}
        model_name = payload.get("model") if isinstance(payload, dict) else None

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

    return app
