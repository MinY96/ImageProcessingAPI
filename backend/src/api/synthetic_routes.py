import io
from typing import Annotated, Callable

import cv2
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response

from src.schemas import ColorSpace
from src.synthetic import (
    SyntheticAssetNotFoundError,
    SyntheticAssetStoreError,
    SyntheticDependencyError,
    SyntheticGenerateRequest,
    SyntheticModelUnavailableError,
    SyntheticValidationError,
)
from src.synthetic.schemas import SyntheticAssetCreateRequest, SyntheticAssetSummary, SyntheticMethodInfo, DiffusionModelStatus

from .errors import ApiRequestError
from .input_codec import decode_upload_image, parse_form_payload
from .models import ResponseFormat
from .output_codec import render_synthetic_result
from .services import ApiServices


def _translate_error(exc: Exception) -> ApiRequestError:
    if isinstance(exc, SyntheticAssetNotFoundError):
        return ApiRequestError(code="synthetic_asset_not_found", message=str(exc), status_code=404)
    if isinstance(exc, SyntheticDependencyError):
        return ApiRequestError(code="synthetic_dependency_unavailable", message=str(exc), status_code=503)
    if isinstance(exc, SyntheticModelUnavailableError):
        return ApiRequestError(code="synthetic_model_unavailable", message=str(exc), status_code=503)
    if isinstance(exc, SyntheticAssetStoreError):
        return ApiRequestError(code="synthetic_asset_store_error", message=str(exc), status_code=500)
    return ApiRequestError(code="synthetic_validation_error", message=str(exc), status_code=422)


def _encode_png(image) -> bytes:
    array = image.data
    if image.color_space == ColorSpace.RGB:
        array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    elif image.color_space == ColorSpace.RGBA:
        array = cv2.cvtColor(array, cv2.COLOR_RGBA2BGRA)
    ok, encoded = cv2.imencode(".png", array)
    if not ok:
        raise ApiRequestError(
            code="output_encoding_failed",
            message="OpenCV could not encode synthetic asset image",
            status_code=500,
        )
    return encoded.tobytes()


def create_synthetic_router(
    prefix: str,
    get_services: Callable[..., ApiServices],
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["synthetic"])

    @router.get("/synthetic/methods", response_model=list[SyntheticMethodInfo])
    def list_methods(services: Annotated[ApiServices, Depends(get_services)]):
        return services.synthetic_service.list_methods()

    @router.get("/synthetic/diffusion/models", response_model=list[DiffusionModelStatus])
    def diffusion_models(services: Annotated[ApiServices, Depends(get_services)]):
        return services.synthetic_service.diffusion_status()

    @router.post("/synthetic/diffusion/unload", status_code=204)
    def unload_diffusion(
        services: Annotated[ApiServices, Depends(get_services)],
        model: Annotated[str | None, Query()] = None,
    ):
        try:
            services.synthetic_service.unload_diffusion(model)
        except SyntheticValidationError as exc:
            raise _translate_error(exc) from exc
        return Response(status_code=204)

    @router.get("/synthetic/assets", response_model=list[SyntheticAssetSummary])
    def list_assets(
        services: Annotated[ApiServices, Depends(get_services)],
        category: Annotated[str | None, Query()] = None,
        search: Annotated[str | None, Query()] = None,
    ):
        return services.synthetic_service.list_assets(category=category, search=search)

    @router.post("/synthetic/assets", response_model=SyntheticAssetSummary, status_code=201)
    def create_asset(
        payload: Annotated[str, Form(description="SyntheticAssetCreateRequest JSON string")],
        image: Annotated[UploadFile, File()],
        services: Annotated[ApiServices, Depends(get_services)],
        mask: Annotated[UploadFile | None, File()] = None,
    ):
        request = parse_form_payload(payload, SyntheticAssetCreateRequest)
        try:
            decoded_image = decode_upload_image(upload=image, settings=services.settings)
            decoded_mask = (
                decode_upload_image(upload=mask, settings=services.settings)
                if mask is not None
                else None
            )
            return services.synthetic_service.add_asset(
                request,
                image=decoded_image,
                mask=decoded_mask,
            )
        except (SyntheticValidationError, SyntheticAssetStoreError) as exc:
            raise _translate_error(exc) from exc

    @router.get("/synthetic/assets/{asset_id}", response_model=SyntheticAssetSummary)
    def get_asset(
        asset_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            return services.synthetic_service.get_asset(asset_id).summary
        except (SyntheticAssetNotFoundError, SyntheticAssetStoreError) as exc:
            raise _translate_error(exc) from exc

    @router.get("/synthetic/assets/{asset_id}/image")
    def get_asset_image(
        asset_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            item = services.synthetic_service.get_asset(asset_id)
            return Response(content=_encode_png(item.image), media_type="image/png")
        except (SyntheticAssetNotFoundError, SyntheticAssetStoreError) as exc:
            raise _translate_error(exc) from exc

    @router.get("/synthetic/assets/{asset_id}/mask")
    def get_asset_mask(
        asset_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            item = services.synthetic_service.get_asset(asset_id)
            if item.mask is None:
                raise ApiRequestError(
                    code="synthetic_asset_mask_not_found",
                    message=f"synthetic asset does not have a mask: {asset_id}",
                    status_code=404,
                )
            return Response(content=_encode_png(item.mask), media_type="image/png")
        except (SyntheticAssetNotFoundError, SyntheticAssetStoreError) as exc:
            raise _translate_error(exc) from exc

    @router.delete("/synthetic/assets/{asset_id}", status_code=204)
    def delete_asset(
        asset_id: str,
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        try:
            services.synthetic_service.delete_asset(asset_id)
        except (SyntheticAssetNotFoundError, SyntheticAssetStoreError) as exc:
            raise _translate_error(exc) from exc
        return Response(status_code=204)

    @router.post("/synthetic/generate")
    def generate(
        payload: Annotated[str, Form(description="SyntheticGenerateRequest JSON string")],
        source_image: Annotated[UploadFile, File()],
        services: Annotated[ApiServices, Depends(get_services)],
        target_mask: Annotated[UploadFile | None, File()] = None,
        asset_image: Annotated[UploadFile | None, File()] = None,
        asset_mask: Annotated[UploadFile | None, File()] = None,
        response_format: Annotated[ResponseFormat, Query()] = ResponseFormat.JSON,
    ):
        request = parse_form_payload(payload, SyntheticGenerateRequest)
        try:
            source = decode_upload_image(upload=source_image, settings=services.settings)
            decoded_target_mask = (
                decode_upload_image(upload=target_mask, settings=services.settings)
                if target_mask is not None
                else None
            )
            decoded_asset = (
                decode_upload_image(upload=asset_image, settings=services.settings)
                if asset_image is not None
                else None
            )
            decoded_asset_mask = (
                decode_upload_image(upload=asset_mask, settings=services.settings)
                if asset_mask is not None
                else None
            )
            result = services.synthetic_service.generate(
                request,
                source=source,
                target_mask=decoded_target_mask,
                asset=decoded_asset,
                asset_mask=decoded_asset_mask,
            )
            return render_synthetic_result(
                result=result,
                response_format=response_format,
                settings=services.settings,
            )
        except (
            SyntheticValidationError,
            SyntheticAssetNotFoundError,
            SyntheticAssetStoreError,
            SyntheticDependencyError,
            SyntheticModelUnavailableError,
        ) as exc:
            raise _translate_error(exc) from exc

    return router
