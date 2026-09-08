from __future__ import annotations

from collections.abc import Iterable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.analysis import ImageAnalyzer
from src.labeling import LabelService, LabelStore
from src.evaluation import (
    EvaluationEngine,
    EvaluationRunStore,
    EvaluationService,
    TestDatasetService,
    TestDatasetStore,
)
from src.pipeline import PipelineCatalog, PipelineExecutor, create_default_pipelines
from src.machine_learning import ModelData, ModelRegistry
from src.recipe import RecipeService, RecipeStore
from src.registry import OperationRegistry, create_default_registry
from src.schemas import PipelineSpec
from src.workflow import (
    WorkflowCatalog,
    WorkflowExecutor,
    create_builtin_graph_recipes,
    create_default_feature_registry,
    create_default_scalar_operator_registry,
)

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

    resolved_pipelines = create_default_pipelines() if pipelines is None else pipelines
    readonly_recipe_names: set[str] = set()
    for pipeline in resolved_pipelines:
        catalog.register(pipeline)
        readonly_recipe_names.add(pipeline.name)

    feature_registry = create_default_feature_registry()
    scalar_operator_registry = create_default_scalar_operator_registry()
    workflow_executor = WorkflowExecutor(
        registry=resolved_registry,
        feature_registry=feature_registry,
        operator_registry=scalar_operator_registry,
        pipeline_executor=executor,
        pipeline_catalog=catalog,
    )
    workflow_catalog = WorkflowCatalog(workflow_executor)
    workflow_executor.attach_workflow_catalog(workflow_catalog)

    readonly_graph_names: set[str] = set()
    # Custom test apps may intentionally replace the default pipeline catalog.
    # Register only graph examples whose dependencies are available.
    for graph in create_builtin_graph_recipes():
        try:
            workflow_catalog.register(graph)
        except Exception:
            if pipelines is None:
                raise
            continue
        readonly_graph_names.add(graph.name)

    recipe_service = RecipeService(
        executor=executor,
        catalog=catalog,
        workflow_executor=workflow_executor,
        workflow_catalog=workflow_catalog,
        store=RecipeStore(resolved_settings.recipe_store_dir),
        readonly_names=readonly_recipe_names,
        readonly_graph_names=readonly_graph_names,
    )
    label_service = LabelService(LabelStore(resolved_settings.label_store_dir))
    test_dataset_service = TestDatasetService(
        TestDatasetStore(resolved_settings.test_dataset_store_dir),
        max_images=resolved_settings.max_test_dataset_images,
    )
    evaluation_engine = EvaluationEngine(
        recipe_service=recipe_service,
        pipeline_executor=executor,
        pipeline_catalog=catalog,
        workflow_executor=workflow_executor,
        workflow_catalog=workflow_catalog,
        max_image_pixels=resolved_settings.max_image_pixels,
    )
    evaluation_service = EvaluationService(
        dataset_service=test_dataset_service,
        engine=evaluation_engine,
        store=EvaluationRunStore(resolved_settings.evaluation_store_dir),
    )

    services = ApiServices(
        registry=resolved_registry,
        feature_registry=feature_registry,
        scalar_operator_registry=scalar_operator_registry,
        image_analyzer=ImageAnalyzer(),
        model_registry=resolved_model_registry,
        pipeline_executor=executor,
        pipeline_catalog=catalog,
        workflow_executor=workflow_executor,
        workflow_catalog=workflow_catalog,
        recipe_service=recipe_service,
        label_service=label_service,
        test_dataset_service=test_dataset_service,
        evaluation_service=evaluation_service,
        settings=resolved_settings,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = services
        yield
        del app.state.services

    app = FastAPI(
        title="Image Processing API",
        version="0.5.0",
        lifespan=lifespan,
    )

    @app.exception_handler(ApiRequestError)
    async def handle_api_request_error(request: Request, exc: ApiRequestError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "HTTP request validation failed",
                    "details": {"issues": jsonable_encoder(exc.errors())},
                }
            },
        )

    app.include_router(create_router(resolved_settings.api_prefix))
    return app
