"""
FastAPI application that proxies requests to LM Studio's REST API v0 and v1.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from api.cache import ModelCacheV0, ModelCacheV1, ModelCache
from api.config import InstanceConfig, ProxyConfig

logger = logging.getLogger(__name__)


def create_app(config: ProxyConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        http_client = httpx.AsyncClient(timeout=config.request_timeout_seconds)
        _app.state.http_client = http_client

        _app.state.model_cache_v0 = ModelCacheV0(http_client, config)
        _app.state.model_cache_v1 = ModelCacheV1(http_client, config)

        logger.info("Lazy-loaded model caches initialized")

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
        cache = request.app.state.model_cache_v0
        return JSONResponse(status_code=200, content=await cache.get_models_response())

    @app.get("/api/v1/models")
    async def list_models_v1(request: Request):
        cache = request.app.state.model_cache_v1
        return JSONResponse(status_code=200, content=await cache.get_models_response())

    @app.get("/api/v0/models/{model_name}")
    async def get_model(request: Request, model_name: str):
        cache = request.app.state.model_cache_v0
        models = await cache.get_models()
        for model in models:
            if model.get("id") == model_name:
                return JSONResponse(status_code=200, content=model)
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

    async def forward_request(request: Request, cache: ModelCache) -> Response:
        http_client: httpx.AsyncClient = request.app.state.http_client

        try:
            payload = await request.json()
        except Exception:
            payload = {}

        model_name = payload.get("model") if isinstance(payload, dict) else None
        is_streaming = payload.get("stream", False) if isinstance(payload, dict) else False

        target = await cache.get_instance_for_model(model_name)
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
            req = http_client.build_request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
            )

            if is_streaming:
                resp = await http_client.send(req, stream=True)

                return StreamingResponse(
                    _stream_generator(resp),
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                    media_type=resp.headers.get("content-type", ""),
                    background=BackgroundTask(resp.aclose),
                )
            else:
                resp = await http_client.send(req)
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Unable to connect to LM Studio")
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Bad gateway")

        content = await resp.aread()
        return Response(
            content=content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
            media_type=resp.headers.get("content-type", ""),
        )

    async def _stream_generator(resp: httpx.Response):
        async for chunk in resp.aiter_bytes():
            yield chunk

    @app.api_route("/api/v0/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_endpoint_v0(request: Request):
        cache = request.app.state.model_cache_v0
        return await forward_request(request, cache)

    @app.api_route("/api/v1/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_endpoint_v1(request: Request):
        cache = request.app.state.model_cache_v1
        return await forward_request(request, cache)

    return app
