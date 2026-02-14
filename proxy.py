"""
FastAPI application that proxies requests to LM Studio's REST API v0.
"""

from __future__ import annotations
import logging
from typing import Dict, List, Optional
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse, JSONResponse

from config import ProxyConfig, InstanceConfig

from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


def create_app(config: ProxyConfig, http_client: httpx.AsyncClient | None = None) -> FastAPI:
    client_owns_http_client = http_client is None
    
    app_state_model_cache: Dict[str, InstanceConfig] = {}
    app_state_all_models: List[dict] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal http_client, app_state_model_cache, app_state_all_models
        if http_client is None:
            http_client = httpx.AsyncClient()
        
        for inst in config.instances:
            try:
                resp = await http_client.get(f"{inst.base_url}/api/v0/models", timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("data", [])
                    for model in models:
                        model_id = model.get("id")
                        if model_id:
                            app_state_model_cache[model_id] = inst
                            model["instance"] = inst.name
                    app_state_all_models.extend(models)
                    logger.info(f"Discovered {len(models)} models from {inst.name} ({inst.base_url})")
                    for model in models:
                        logger.debug(f"  - {model.get('id')} ({model.get('type')}, {model.get('quantization')}, {model.get('state')})")
            except Exception as e:
                logger.warning(f"Failed to fetch models from {inst.name} ({inst.base_url}): {e}")
        
        app.state.model_cache = app_state_model_cache
        app.state.all_models = app_state_all_models
        
        logger.info(f"Auto-discovery complete: {len(app_state_model_cache)} total models from {len(config.instances)} instances")
        
        yield
        
        if client_owns_http_client and http_client:
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
    async def list_models(request: Request):
        all_models = getattr(request.app.state, "all_models", [])
        return JSONResponse(status_code=200, content={"object": "list", "data": all_models})

    @app.get("/api/v0/models/{model_name}")
    async def get_model(request: Request, model_name: str):
        all_models = getattr(request.app.state, "all_models", [])
        for model in all_models:
            if model.get("id") == model_name:
                return JSONResponse(status_code=200, content=model)
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

    async def forward_request(request: Request, target_base_url: str) -> Response:
        nonlocal http_client
        path = request.url.path
        url = f"{target_base_url}{path}"

        headers: Dict[str, str] = {
            key: value for key, value in request.headers.items() if key.lower() in {"authorization", "content-type"}
        }

        body = await request.body()

        if http_client is None:
            http_client = httpx.AsyncClient()
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
        return Response(content=content, status_code=resp.status_code, headers=dict(resp.headers), media_type=content_type)

    @app.api_route("/api/v0/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_endpoint(request: Request):
        model_cache = getattr(request.app.state, "model_cache", {})
        
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        model_name = payload.get("model") if isinstance(payload, dict) else None

        target: Optional[InstanceConfig] = None
        if model_name and model_name in model_cache:
            target = model_cache[model_name]
        
        if not target and config.fallback_instance:
            target = next((i for i in config.instances if i.name == config.fallback_instance), None)

        if not target:
            raise HTTPException(status_code=400, detail=f"Model '{model_name}' not found and no fallback defined")

        return await forward_request(request, target.base_url)

    return app
