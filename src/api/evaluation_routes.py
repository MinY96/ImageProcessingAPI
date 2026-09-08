from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from src.evaluation import (
    AddImagesRequest,
    BatchGroundTruthRequest,
    DuplicateTestDatasetError,
    EvaluationPrediction,
    EvaluationRequest,
    EvaluationResultPage,
    EvaluationRun,
    EvaluationRunNotFoundError,
    EvaluationRunSummary,
    EvaluationStoreError,
    EvaluationValidationError,
    FolderImportRequest,
    FolderImportResult,
    GroundTruthLabel,
    TestDatasetCreateRequest,
    TestDatasetImageNotFoundError,
    TestDatasetImagePage,
    TestDatasetNotFoundError,
    TestDatasetRecord,
    TestDatasetRevisionConflictError,
    TestDatasetStoreError,
    TestDatasetSummary,
    TestDatasetUpdateRequest,
    UpdateTestImageRequest,
)
from src.recipe import RecipeNotFoundError

from .errors import ApiRequestError
from .services import ApiServices


def _evaluation_error(exc: Exception) -> ApiRequestError:
    if isinstance(exc, (TestDatasetNotFoundError, TestDatasetImageNotFoundError, EvaluationRunNotFoundError, RecipeNotFoundError)):
        return ApiRequestError(code="evaluation_resource_not_found", message=str(exc), status_code=404)
    if isinstance(exc, DuplicateTestDatasetError):
        return ApiRequestError(code="test_dataset_already_exists", message=str(exc), status_code=409)
    if isinstance(exc, TestDatasetRevisionConflictError):
        return ApiRequestError(code="test_dataset_revision_conflict", message=str(exc), status_code=409)
    if isinstance(exc, EvaluationValidationError):
        return ApiRequestError(code="evaluation_validation_error", message=str(exc), status_code=422)
    if isinstance(exc, ValueError):
        return ApiRequestError(code="test_dataset_validation_error", message=str(exc), status_code=422)
    if isinstance(exc, (TestDatasetStoreError, EvaluationStoreError)):
        return ApiRequestError(code="evaluation_store_error", message="evaluation storage operation failed", status_code=500)
    return ApiRequestError(code="evaluation_error", message=str(exc), status_code=500)


def create_evaluation_router(prefix: str, get_services) -> APIRouter:
    router = APIRouter(prefix=prefix)

    datasets = APIRouter(prefix="/test-datasets", tags=["test-datasets"])

    @datasets.get("", response_model=list[TestDatasetSummary])
    def list_test_datasets(
        services: Annotated[ApiServices, Depends(get_services)],
        search: Annotated[str | None, Query(min_length=1, max_length=256)] = None,
    ):
        try:
            return services.test_dataset_service.list(search=search)
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @datasets.post("", response_model=TestDatasetRecord, status_code=status.HTTP_201_CREATED)
    def create_test_dataset(
        request: TestDatasetCreateRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.test_dataset_service.create(request)
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @datasets.get("/{dataset_id}", response_model=TestDatasetSummary)
    def get_test_dataset(
        dataset_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.test_dataset_service.summarize(services.test_dataset_service.get(dataset_id))
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @datasets.get("/{dataset_id}/images", response_model=TestDatasetImagePage)
    def list_test_dataset_images(
        dataset_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        ground_truth: Annotated[GroundTruthLabel | None, Query()] = None,
        unlabeled_only: Annotated[bool, Query()] = False,
        search: Annotated[str | None, Query(min_length=1, max_length=256)] = None,
    ):
        try:
            return services.test_dataset_service.list_images(
                dataset_id,
                offset=offset,
                limit=limit,
                ground_truth=ground_truth,
                unlabeled_only=unlabeled_only,
                search=search,
            )
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @datasets.put("/{dataset_id}", response_model=TestDatasetRecord)
    def update_test_dataset(
        dataset_id: str,
        request: TestDatasetUpdateRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.test_dataset_service.update(dataset_id, request)
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @datasets.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_test_dataset(
        dataset_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
        expected_revision: Annotated[int | None, Query(ge=1)] = None,
    ) -> Response:
        try:
            services.test_dataset_service.delete(dataset_id, expected_revision=expected_revision)
        except Exception as exc:
            raise _evaluation_error(exc) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @datasets.post("/{dataset_id}/import-folder", response_model=FolderImportResult)
    def import_test_dataset_folder(
        dataset_id: str,
        request: FolderImportRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.test_dataset_service.import_folder(dataset_id, request)
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @datasets.post("/{dataset_id}/images", response_model=TestDatasetSummary)
    def add_test_dataset_images(
        dataset_id: str,
        request: AddImagesRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.test_dataset_service.summarize(services.test_dataset_service.add_images(dataset_id, request))
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @datasets.put("/{dataset_id}/images/{image_id}", response_model=TestDatasetSummary)
    def update_test_dataset_image(
        dataset_id: str,
        image_id: str,
        request: UpdateTestImageRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.test_dataset_service.summarize(services.test_dataset_service.update_image(dataset_id, image_id, request))
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @datasets.delete("/{dataset_id}/images/{image_id}", response_model=TestDatasetSummary)
    def delete_test_dataset_image(
        dataset_id: str,
        image_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
        expected_revision: Annotated[int | None, Query(ge=1)] = None,
    ):
        try:
            return services.test_dataset_service.summarize(services.test_dataset_service.delete_image(dataset_id, image_id, expected_revision=expected_revision))
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @datasets.put("/{dataset_id}/ground-truth", response_model=TestDatasetSummary)
    def batch_update_ground_truth(
        dataset_id: str,
        request: BatchGroundTruthRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.test_dataset_service.summarize(services.test_dataset_service.batch_ground_truth(dataset_id, request))
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    evaluations = APIRouter(prefix="/evaluations", tags=["evaluations"])

    @evaluations.get("", response_model=list[EvaluationRunSummary])
    def list_evaluations(
        services: Annotated[ApiServices, Depends(get_services)],
        dataset_id: Annotated[str | None, Query()] = None,
        recipe_name: Annotated[str | None, Query()] = None,
    ):
        try:
            return services.evaluation_service.list(dataset_id=dataset_id, recipe_name=recipe_name)
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @evaluations.post("", response_model=EvaluationRun, status_code=status.HTTP_201_CREATED)
    def create_evaluation(
        request: EvaluationRequest,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.evaluation_service.create(request)
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @evaluations.get("/{evaluation_id}", response_model=EvaluationRun)
    def get_evaluation(
        evaluation_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.evaluation_service.get(evaluation_id)
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    @evaluations.delete("/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_evaluation(
        evaluation_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ) -> Response:
        try:
            services.evaluation_service.delete(evaluation_id)
        except Exception as exc:
            raise _evaluation_error(exc) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @evaluations.get("/{evaluation_id}/results", response_model=EvaluationResultPage)
    def get_evaluation_results(
        evaluation_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        prediction: Annotated[EvaluationPrediction | None, Query()] = None,
        ground_truth: Annotated[GroundTruthLabel | None, Query()] = None,
        correct: Annotated[bool | None, Query()] = None,
        errors_only: Annotated[bool, Query()] = False,
    ):
        try:
            return services.evaluation_service.results(
                evaluation_id,
                offset=offset,
                limit=limit,
                prediction=prediction,
                ground_truth=ground_truth,
                correct=correct,
                errors_only=errors_only,
            )
        except Exception as exc:
            raise _evaluation_error(exc) from exc

    router.include_router(datasets)
    router.include_router(evaluations)
    return router
