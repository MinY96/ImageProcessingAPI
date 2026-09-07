
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from src.pipeline import PipelineNotFoundError, PipelineValidationError
from src.recipe import (
    DuplicateRecipeError,
    ReadonlyRecipeError,
    RecipeCloneRequest,
    RecipeCreateRequest,
    RecipeNotFoundError,
    RecipeRecord,
    RecipeRevisionConflictError,
    RecipeSource,
    RecipeStoreError,
    RecipeSummary,
    RecipeUpdateRequest,
)

from .errors import ApiRequestError
from .input_codec import decode_request_inputs, parse_form_payload
from .models import PipelineRunPayload, ResponseFormat
from .output_codec import render_pipeline_result
from .services import ApiServices


def _recipe_error(exc: Exception) -> ApiRequestError:
    if isinstance(exc, RecipeNotFoundError):
        return ApiRequestError(
            code="recipe_not_found",
            message=str(exc),
            status_code=404,
        )
    if isinstance(exc, DuplicateRecipeError):
        return ApiRequestError(
            code="recipe_already_exists",
            message=str(exc),
            status_code=409,
        )
    if isinstance(exc, ReadonlyRecipeError):
        return ApiRequestError(
            code="readonly_recipe",
            message=str(exc),
            status_code=403,
        )
    if isinstance(exc, RecipeRevisionConflictError):
        return ApiRequestError(
            code="recipe_revision_conflict",
            message=str(exc),
            status_code=409,
        )
    if isinstance(exc, PipelineValidationError):
        return ApiRequestError(
            code="pipeline_validation_error",
            message="recipe pipeline validation failed",
            status_code=422,
            details=exc.to_dict(),
        )
    if isinstance(exc, ValueError):
        return ApiRequestError(
            code="recipe_validation_error",
            message=str(exc),
            status_code=422,
        )
    if isinstance(exc, RecipeStoreError):
        return ApiRequestError(
            code="recipe_store_error",
            message="recipe storage operation failed",
            status_code=500,
        )
    return ApiRequestError(
        code="recipe_error",
        message=str(exc),
        status_code=500,
    )


def create_recipe_router(prefix: str, get_services) -> APIRouter:
    router = APIRouter(prefix=f"{prefix}/recipes", tags=["recipes"])

    @router.get("", response_model=list[RecipeSummary])
    def list_recipes(
        services: Annotated[ApiServices, Depends(get_services)],
        source: Annotated[RecipeSource | None, Query()] = None,
        tag: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
        search: Annotated[str | None, Query(min_length=1, max_length=256)] = None,
    ):
        return services.recipe_service.list(source=source, tag=tag, search=search)

    @router.post("", response_model=RecipeRecord, status_code=status.HTTP_201_CREATED)
    def create_recipe(
        request: RecipeCreateRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.recipe_service.create(request)
        except Exception as exc:
            raise _recipe_error(exc) from exc

    @router.post(
        "/{recipe_name}/clone",
        response_model=RecipeRecord,
        status_code=status.HTTP_201_CREATED,
    )
    def clone_recipe(
        recipe_name: str,
        request: RecipeCloneRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.recipe_service.clone(recipe_name, request)
        except Exception as exc:
            raise _recipe_error(exc) from exc

    @router.get("/{recipe_name}", response_model=RecipeRecord)
    def get_recipe(
        recipe_name: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.recipe_service.get(recipe_name)
        except Exception as exc:
            raise _recipe_error(exc) from exc

    @router.put("/{recipe_name}", response_model=RecipeRecord)
    def update_recipe(
        recipe_name: str,
        request: RecipeUpdateRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.recipe_service.update(recipe_name, request)
        except Exception as exc:
            raise _recipe_error(exc) from exc

    @router.delete("/{recipe_name}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_recipe(
        recipe_name: str,
        services: Annotated[ApiServices, Depends(get_services)],
        expected_revision: Annotated[int | None, Query(ge=1)] = None,
    ) -> Response:
        try:
            services.recipe_service.delete(
                recipe_name,
                expected_revision=expected_revision,
            )
        except Exception as exc:
            raise _recipe_error(exc) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{recipe_name}/execute")
    def execute_recipe(
        recipe_name: str,
        payload: Annotated[
            str,
            Form(description="PipelineRunPayload JSON string."),
        ],
        services: Annotated[ApiServices, Depends(get_services)],
        files: Annotated[list[UploadFile] | None, File()] = None,
        response_format: Annotated[ResponseFormat, Query()] = ResponseFormat.JSON,
    ):
        try:
            services.recipe_service.get(recipe_name)
            compiled = services.pipeline_catalog.get(recipe_name)
        except (RecipeNotFoundError, PipelineNotFoundError) as exc:
            raise ApiRequestError(
                code="recipe_not_found",
                message=f"recipe does not exist: {recipe_name}",
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

    return router
