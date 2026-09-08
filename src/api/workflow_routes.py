from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from src.workflow import GraphRecipeSpec, WorkflowValidationError, WorkflowValidationResponse

from .errors import ApiRequestError
from .input_codec import decode_request_inputs, parse_form_payload
from .models import AdHocWorkflowRunPayload, ResponseFormat
from .output_codec import render_workflow_result
from .services import ApiServices


def create_workflow_router(prefix: str, get_services) -> APIRouter:
    router = APIRouter(prefix=f"{prefix}/workflow", tags=["workflow"])

    @router.get("/features")
    def list_features(services: Annotated[ApiServices, Depends(get_services)]):
        return services.feature_registry.list_specs()

    @router.get("/operators")
    def list_scalar_operators(services: Annotated[ApiServices, Depends(get_services)]):
        return services.scalar_operator_registry.list_specs()

    @router.post("/validate", response_model=WorkflowValidationResponse)
    def validate_workflow(
        graph: GraphRecipeSpec,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            compiled = services.workflow_executor.compile(graph)
        except WorkflowValidationError as exc:
            return JSONResponse(
                status_code=422,
                content=WorkflowValidationResponse(
                    valid=False,
                    recipe=graph.name,
                    error=exc.to_dict(),
                ).model_dump(mode="json"),
            )
        return WorkflowValidationResponse(
            valid=True,
            recipe=compiled.spec.name,
            execution_order=list(compiled.execution_order),
            output_names=sorted(compiled.output_bindings),
        )

    @router.post("/execute")
    def execute_ad_hoc_workflow(
        payload: Annotated[str, Form(description="AdHocWorkflowRunPayload JSON string.")],
        services: Annotated[ApiServices, Depends(get_services)],
        files: Annotated[list[UploadFile] | None, File()] = None,
        response_format: ResponseFormat = ResponseFormat.JSON,
    ):
        parsed = parse_form_payload(payload, AdHocWorkflowRunPayload)
        inputs = decode_request_inputs(
            payload=parsed,
            files=files or [],
            settings=services.settings,
            model_registry=services.model_registry,
        )
        result = services.workflow_executor.execute(
            recipe=parsed.graph,
            inputs=inputs,
            retain_intermediates=parsed.retain_intermediates,
        )
        return render_workflow_result(
            result=result,
            response_format=response_format,
            settings=services.settings,
            analyzer=services.image_analyzer,
            analysis_options=parsed.analysis,
            analyze_intermediates=parsed.analyze_intermediates,
        )

    return router
