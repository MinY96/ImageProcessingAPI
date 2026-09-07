from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse

from src.pipeline import (
    PipelineNotFoundError,
    PipelineValidationError,
)
from src.machine_learning import ModelNotFoundError, ModelSpec
from src.registry import OperationNotFoundError
from src.schemas import OperationSpec, PipelineSpec

from .errors import ApiRequestError
from .input_codec import decode_request_inputs, parse_form_payload
from .label_routes import create_label_router
from .models import (
    AdHocPipelineRunPayload,
    OperationRunPayload,
    PipelineRunPayload,
    PipelineValidationResponse,
    ResponseFormat,
)
from .recipe_routes import create_recipe_router
from .output_codec import (
    render_operation_result,
    render_pipeline_result,
)
from .services import ApiServices


def get_services(request: Request) -> ApiServices:
    return request.app.state.services


def create_router(prefix: str) -> APIRouter:
    router = APIRouter(prefix=prefix)

    @router.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get(
        "/operations",
        response_model=list[OperationSpec],
        tags=["operations"],
    )
    def list_operations(
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        return services.registry.list_specs()

    @router.get(
        "/operations/{operation}",
        response_model=OperationSpec,
        tags=["operations"],
    )
    def get_operation(
        operation: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.registry.get_spec(operation)
        except OperationNotFoundError as exc:
            raise ApiRequestError(
                code="operation_not_found",
                message=str(exc),
                status_code=404,
            ) from exc

    @router.get(
        "/models",
        response_model=list[ModelSpec],
        tags=["models"],
    )
    def list_models(
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        return services.model_registry.list_specs()

    @router.get(
        "/models/{model_id}/{version}",
        response_model=ModelSpec,
        tags=["models"],
    )
    def get_model(
        model_id: str,
        version: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.model_registry.get(model_id, version).spec
        except ModelNotFoundError as exc:
            raise ApiRequestError(
                code="model_not_found",
                message=str(exc),
                status_code=404,
            ) from exc

    @router.post(
        "/operations/{operation}/execute",
        tags=["operations"],
    )
    def execute_operation(
        operation: str,
        payload: Annotated[
            str,
            Form(
                description=(
                    "OperationRunPayload JSON string. Files are bound "
                    "through image_inputs[].file_index."
                )
            ),
        ],
        services: Annotated[ApiServices, Depends(get_services)],
        files: Annotated[list[UploadFile] | None, File()] = None,
        response_format: Annotated[
            ResponseFormat,
            Query(),
        ] = ResponseFormat.JSON,
    ):
        if not services.registry.contains(operation):
            raise ApiRequestError(
                code="operation_not_found",
                message=f"operation is not registered: {operation}",
                status_code=404,
            )

        parsed = parse_form_payload(payload, OperationRunPayload)
        inputs = decode_request_inputs(
            payload=parsed,
            files=files or [],
            settings=services.settings,
            model_registry=services.model_registry,
        )
        result = services.registry.execute(
            operation=operation,
            inputs=inputs,
            params=parsed.params,
        )
        return render_operation_result(
            result=result,
            response_format=response_format,
            settings=services.settings,
        )

    @router.get(
        "/pipelines",
        response_model=list[PipelineSpec],
        tags=["pipelines"],
    )
    def list_pipelines(
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        return services.pipeline_catalog.list_specs()

    @router.post(
        "/pipelines/validate",
        response_model=PipelineValidationResponse,
        tags=["pipelines"],
    )
    def validate_pipeline(
        pipeline: PipelineSpec,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            compiled = services.pipeline_executor.compile(pipeline)
        except PipelineValidationError as exc:
            return JSONResponse(
                status_code=422,
                content=PipelineValidationResponse(
                    valid=False,
                    pipeline=pipeline.name,
                    error=exc.to_dict(),
                ).model_dump(mode="json"),
            )

        return PipelineValidationResponse(
            valid=True,
            pipeline=compiled.spec.name,
            registry_revision=compiled.registry_revision,
            output_names=sorted(compiled.output_bindings),
        )

    @router.post(
        "/pipelines/execute",
        tags=["pipelines"],
    )
    def execute_ad_hoc_pipeline(
        payload: Annotated[
            str,
            Form(description="AdHocPipelineRunPayload JSON string."),
        ],
        services: Annotated[ApiServices, Depends(get_services)],
        files: Annotated[list[UploadFile] | None, File()] = None,
        response_format: Annotated[
            ResponseFormat,
            Query(),
        ] = ResponseFormat.JSON,
    ):
        parsed = parse_form_payload(payload, AdHocPipelineRunPayload)
        inputs = decode_request_inputs(
            payload=parsed,
            files=files or [],
            settings=services.settings,
            model_registry=services.model_registry,
        )
        result = services.pipeline_executor.execute(
            pipeline=parsed.pipeline,
            inputs=inputs,
            retain_intermediates=parsed.retain_intermediates,
        )
        return render_pipeline_result(
            result=result,
            response_format=response_format,
            settings=services.settings,
        )

    @router.get(
        "/pipelines/{pipeline_name}",
        response_model=PipelineSpec,
        tags=["pipelines"],
    )
    def get_pipeline(
        pipeline_name: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.pipeline_catalog.get_spec(pipeline_name)
        except PipelineNotFoundError as exc:
            raise ApiRequestError(
                code="pipeline_not_found",
                message=str(exc),
                status_code=404,
            ) from exc

    @router.post(
        "/pipelines/{pipeline_name}/execute",
        tags=["pipelines"],
    )
    def execute_registered_pipeline(
        pipeline_name: str,
        payload: Annotated[
            str,
            Form(description="PipelineRunPayload JSON string."),
        ],
        services: Annotated[ApiServices, Depends(get_services)],
        files: Annotated[list[UploadFile] | None, File()] = None,
        response_format: Annotated[
            ResponseFormat,
            Query(),
        ] = ResponseFormat.JSON,
    ):
        try:
            compiled = services.pipeline_catalog.get(pipeline_name)
        except PipelineNotFoundError as exc:
            raise ApiRequestError(
                code="pipeline_not_found",
                message=str(exc),
                status_code=404,
            ) from exc

        parsed = parse_form_payload(payload, PipelineRunPayload)
        inputs = decode_request_inputs(
            payload=parsed,
            files=files or [],
            settings=services.settings,
            model_registry=services.model_registry,
        )
        result = services.pipeline_executor.execute(
            pipeline=compiled,
            inputs=inputs,
            retain_intermediates=parsed.retain_intermediates,
        )
        return render_pipeline_result(
            result=result,
            response_format=response_format,
            settings=services.settings,
        )

    router.include_router(create_recipe_router("", get_services))
    router.include_router(create_label_router("", get_services))
    return router
