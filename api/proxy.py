"""
FastAPI application that proxies requests to LM Studio's REST API v0 and v1.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from api.config import InstanceConfig, ProxyConfig

logger = logging.getLogger(__name__)


def create_app(config: ProxyConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        http_client = httpx.AsyncClient()
        _app.state.http_client = http_client

        model_routing_cache: Dict[str, InstanceConfig] = {}
        all_models_v0: List[dict] = []
        all_models_v1: List[dict] = []
        instances_to_discover = sorted(
            config.instances,
            key=lambda i: 0 if i.name == config.fallback_instance else 1
        )

        for inst in instances_to_discover:
            try:
                resp_v1 = await http_client.get(f"{inst.base_url}/api/v1/models", timeout=10.0)
                if resp_v1.status_code == 200:
                    data = resp_v1.json()
                    models = data.get("models", [])
                    for model in models:
                        model_id = model.get("key")
                        if model_id:
                            model_routing_cache[model_id] = inst
                    all_models_v1.extend(models)
                    logger.info(f"Discovered {len(models)} models from {inst.name} ({inst.base_url}) via v1")
                    for model in models:
                        logger.debug(
                            f"  - {model.get('id')} ({model.get('type')}, {model.get('quantization')}, {model.get('state')})")
            except Exception as e:
                logger.warning(f"Failed to fetch v1 models from {inst.name} ({inst.base_url}): {e}")

            try:
                resp_v0 = await http_client.get(f"{inst.base_url}/api/v0/models", timeout=10.0)
                if resp_v0.status_code == 200:
                    data = resp_v0.json()
                    models = data.get("data", [])
                    all_models_v0.extend(models)
                    logger.info(f"Discovered {len(models)} models from {inst.name} ({inst.base_url}) via v0")
            except Exception as e:
                logger.warning(f"Failed to fetch v0 models from {inst.name} ({inst.base_url}): {e}")

        _app.state.model_routing_cache = model_routing_cache
        _app.state.all_models_v0 = all_models_v0
        _app.state.all_models_v1 = all_models_v1

        logger.info(f"Auto-discovery complete: {len(model_routing_cache)} total models from {len(config.instances)} instances")

        yield

        await http_client.aclose()

    app = FastAPI(title="LM Studio Proxy", lifespan=lifespan)

    @app.middleware("http")
    async def add_headers(request: Request, call_next):
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"message": str(exc)})

    @app.exception_handler(Exception)
    async def generic_exception_handler(_: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"message": "Internal server error"})

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/api/v0/models")
    async def list_models_v0(request: Request):
        all_models = getattr(request.app.state, "all_models_v0", [])
        return JSONResponse(status_code=200, content={"object": "list", "data": all_models})

    @app.get("/api/v1/models")
    async def list_models_v1(request: Request):
        all_models = getattr(request.app.state, "all_models_v1", [])
        return JSONResponse(status_code=200, content={"models": all_models})

    @app.get("/api/v0/models/{model_name}")
    async def get_model(request: Request, model_name: str):
        all_models = getattr(request.app.state, "all_models_v0", [])
        for model in all_models:
            if model.get("id") == model_name:
                return JSONResponse(status_code=200, content=model)
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

    async def forward_request(request: Request) -> Response:
        http_client: httpx.AsyncClient = request.app.state.http_client
        model_routing_cache = getattr(request.app.state, "model_routing_cache", {})

        try:
            payload = await request.json()
        except Exception:
            payload = {}
        model_name = payload.get("model") if isinstance(payload, dict) else None
        if not model_name:
            raise HTTPException(status_code=400, detail="Missing model name in request body, unable to proxy request")

        target: Optional[InstanceConfig] = None
        if model_name in model_routing_cache:
            target = model_routing_cache[model_name]

        if not target and config.fallback_instance:
            target = next((i for i in config.instances if i.name == config.fallback_instance), None)

        if not target:
            raise HTTPException(status_code=400, detail=f"Model '{model_name}' not found and no fallback defined")

        logger.info(f"Redirecting request for model {model_name} to {target.name}...")
        path = request.url.path
        url = f"{target.base_url}{path}"

        headers: Dict[str, str] = {
            key: value for key, value in request.headers.items() if key.lower() in {"authorization", "content-type"}
        }

        body = await request.body()

        try:
            resp = await http_client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                timeout=None,
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Unable to connect to LM Studio")
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Bad gateway")

        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return StreamingResponse(
                resp.aiter_bytes(),
                status_code=resp.status_code,
                headers=dict(resp.headers),
                media_type=content_type,
            )

        content = await resp.aread()
        return Response(content=content,
                        status_code=resp.status_code,
                        headers=dict(resp.headers),
                        media_type=content_type)

    @app.api_route("/api/v0/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_endpoint_v0(request: Request):
        return await forward_request(request)

    @app.api_route("/api/v1/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_endpoint_v1(request: Request):
        return await forward_request(request)

    return app
