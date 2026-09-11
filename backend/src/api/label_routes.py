
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from src.labeling import (
    AnnotationCreateRequest,
    AnnotationNotFoundError,
    AnnotationUpdateRequest,
    DuplicateAnnotationError,
    DuplicateLabelError,
    LabelClassSummary,
    LabelCreateRequest,
    LabelDocument,
    LabelListResponse,
    LabelNotFoundError,
    LabelRevisionConflictError,
    LabelStoreError,
    LabelUpdateRequest,
)

from .errors import ApiRequestError
from .services import ApiServices


def _label_error(exc: Exception) -> ApiRequestError:
    if isinstance(exc, LabelNotFoundError):
        return ApiRequestError(
            code="label_not_found",
            message=str(exc),
            status_code=404,
        )
    if isinstance(exc, AnnotationNotFoundError):
        return ApiRequestError(
            code="annotation_not_found",
            message=str(exc),
            status_code=404,
        )
    if isinstance(exc, DuplicateLabelError):
        return ApiRequestError(
            code="label_already_exists",
            message=str(exc),
            status_code=409,
        )
    if isinstance(exc, DuplicateAnnotationError):
        return ApiRequestError(
            code="annotation_already_exists",
            message=str(exc),
            status_code=409,
        )
    if isinstance(exc, LabelRevisionConflictError):
        return ApiRequestError(
            code="label_revision_conflict",
            message=str(exc),
            status_code=409,
        )
    if isinstance(exc, LabelStoreError):
        return ApiRequestError(
            code="label_store_error",
            message="label storage operation failed",
            status_code=500,
        )
    if isinstance(exc, ValueError):
        return ApiRequestError(
            code="label_validation_error",
            message=str(exc),
            status_code=422,
        )
    return ApiRequestError(
        code="label_error",
        message=str(exc),
        status_code=500,
    )


def create_label_router(prefix: str, get_services) -> APIRouter:
    router = APIRouter(prefix=f"{prefix}/labels", tags=["labels"])

    @router.get("", response_model=LabelListResponse)
    def list_labels(
        services: Annotated[ApiServices, Depends(get_services)],
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        label: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
        tag: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
        search: Annotated[str | None, Query(min_length=1, max_length=256)] = None,
    ):
        try:
            return services.label_service.list(
                offset=offset,
                limit=limit,
                label=label,
                tag=tag,
                search=search,
            )
        except Exception as exc:
            raise _label_error(exc) from exc

    @router.post("", response_model=LabelDocument, status_code=status.HTTP_201_CREATED)
    def create_label(
        request: LabelCreateRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.label_service.create(request)
        except Exception as exc:
            raise _label_error(exc) from exc

    @router.get("/classes", response_model=list[LabelClassSummary])
    def list_label_classes(
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.label_service.list_classes()
        except Exception as exc:
            raise _label_error(exc) from exc

    @router.get("/{image_id}", response_model=LabelDocument)
    def get_label(
        image_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.label_service.get(image_id)
        except Exception as exc:
            raise _label_error(exc) from exc

    @router.put("/{image_id}", response_model=LabelDocument)
    def update_label(
        image_id: str,
        request: LabelUpdateRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.label_service.update(image_id, request)
        except Exception as exc:
            raise _label_error(exc) from exc

    @router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_label(
        image_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
        expected_revision: Annotated[int | None, Query(ge=1)] = None,
    ) -> Response:
        try:
            services.label_service.delete(image_id, expected_revision=expected_revision)
        except Exception as exc:
            raise _label_error(exc) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{image_id}/annotations", response_model=LabelDocument)
    def add_annotation(
        image_id: str,
        request: AnnotationCreateRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.label_service.add_annotation(
                image_id,
                request.annotation,
                expected_revision=request.expected_revision,
            )
        except Exception as exc:
            raise _label_error(exc) from exc

    @router.put("/{image_id}/annotations/{annotation_id}", response_model=LabelDocument)
    def update_annotation(
        image_id: str,
        annotation_id: str,
        request: AnnotationUpdateRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.label_service.update_annotation(
                image_id,
                annotation_id,
                request.annotation,
                expected_revision=request.expected_revision,
            )
        except Exception as exc:
            raise _label_error(exc) from exc

    @router.delete("/{image_id}/annotations/{annotation_id}", response_model=LabelDocument)
    def delete_annotation(
        image_id: str,
        annotation_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
        expected_revision: Annotated[int | None, Query(ge=1)] = None,
    ):
        try:
            return services.label_service.delete_annotation(
                image_id,
                annotation_id,
                expected_revision=expected_revision,
            )
        except Exception as exc:
            raise _label_error(exc) from exc

    return router
