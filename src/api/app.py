from __future__ import annotations

from collections.abc import Iterable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.pipeline import (
    PipelineCatalog,
    PipelineExecutor,
    create_default_pipelines,
)
from src.machine_learning import ModelData, ModelRegistry
from src.registry import OperationRegistry, create_default_registry
from src.schemas import PipelineSpec

from .config import ApiSettings
from .errors import ApiRequestError
from .routes import create_router
from .services import ApiServices


def create_app(
    *,
    registry: OperationRegistry | None = None,
    pipelines: Iterable[PipelineSpec] | None = None,
    models: Iterable[ModelData] | None = None,
    model_registry: ModelRegistry | None = None,
    settings: ApiSettings | None = None,
) -> FastAPI:
    resolved_registry = registry or create_default_registry()
    resolved_settings = settings or ApiSettings()
    executor = PipelineExecutor(resolved_registry)
    catalog = PipelineCatalog(executor)
    resolved_model_registry = model_registry or ModelRegistry()
    for model in models or ():
        resolved_model_registry.register(model)

    resolved_pipelines = (
        create_default_pipelines()
        if pipelines is None
        else pipelines
    )
    for pipeline in resolved_pipelines:
        catalog.register(pipeline)

    services = ApiServices(
        registry=resolved_registry,
        model_registry=resolved_model_registry,
        pipeline_executor=executor,
        pipeline_catalog=catalog,
        settings=resolved_settings,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = services
        yield
        del app.state.services

    app = FastAPI(
        title="Image Processing API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(ApiRequestError)
    async def handle_api_request_error(
        request: Request,
        exc: ApiRequestError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "HTTP request validation failed",
                    "details": {
                        "issues": jsonable_encoder(exc.errors())
                    },
                }
            },
        )

    app.include_router(
        create_router(resolved_settings.api_prefix)
    )
    return app
