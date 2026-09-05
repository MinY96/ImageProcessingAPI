from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import cv2
import numpy as np
from fastapi import UploadFile
from pydantic import BaseModel, ValidationError

from src.schemas import ColorSpace, ImageData
from src.machine_learning import ModelNotFoundError, ModelRegistry

from .config import ApiSettings
from .errors import ApiRequestError
from .models import ImageUploadBinding, InputPayloadBase


def parse_form_payload[
    ModelT: BaseModel
](payload: str, model_type: type[ModelT]) -> ModelT:
    try:
        return model_type.model_validate_json(payload)
    except ValidationError as exc:
        raise ApiRequestError(
            code="invalid_payload",
            message="multipart payload is invalid",
            details={"issues": exc.errors(include_url=False)},
        ) from exc


def decode_request_inputs(
    *,
    payload: InputPayloadBase,
    files: Sequence[UploadFile],
    settings: ApiSettings,
    model_registry: ModelRegistry,
) -> dict[str, Any]:
    if len(files) > settings.max_upload_files:
        raise ApiRequestError(
            code="too_many_files",
            message="too many uploaded files",
            status_code=413,
            details={
                "provided": len(files),
                "maximum": settings.max_upload_files,
            },
        )

    used_indices = {
        binding.file_index
        for binding in payload.image_inputs
    }

    invalid_indices = sorted(
        index
        for index in used_indices
        if index >= len(files)
    )
    if invalid_indices:
        raise ApiRequestError(
            code="invalid_file_index",
            message="image binding references a missing file",
            details={"file_indices": invalid_indices},
        )

    unused_indices = sorted(set(range(len(files))) - used_indices)
    if unused_indices:
        raise ApiRequestError(
            code="unused_upload",
            message="uploaded files must have an image input binding",
            details={"file_indices": unused_indices},
        )

    decoded_cache: dict[int, tuple[np.ndarray, ColorSpace, str | None]] = {}
    result = dict(payload.inputs)

    for binding in payload.model_inputs:
        try:
            result[binding.input_name] = model_registry.get(
                binding.model_id, binding.version
            )
        except ModelNotFoundError as exc:
            raise ApiRequestError(
                code="model_not_found",
                message=str(exc),
                status_code=404,
                details={
                    "model_id": binding.model_id,
                    "version": binding.version,
                },
            ) from exc

    total_decoded_bytes = 0

    for binding in payload.image_inputs:
        if binding.file_index not in decoded_cache:
            decoded = _decode_upload(
                upload=files[binding.file_index],
                settings=settings,
            )
            decoded_cache[binding.file_index] = decoded
            total_decoded_bytes += decoded[0].nbytes

            if total_decoded_bytes > settings.max_total_decoded_bytes:
                raise ApiRequestError(
                    code="decoded_input_limit_exceeded",
                    message="decoded image inputs exceed the memory limit",
                    status_code=413,
                    details={
                        "decoded_bytes": total_decoded_bytes,
                        "maximum": settings.max_total_decoded_bytes,
                    },
                )

        array, inferred_color_space, filename = decoded_cache[
            binding.file_index
        ]

        color_space = _resolve_color_space(
            requested=binding.color_space,
            inferred=inferred_color_space,
            array=array,
        )
        result[binding.input_name] = ImageData(
            data=array,
            color_space=color_space,
            name=binding.name or filename,
        )

    return result


def _decode_upload(
    *,
    upload: UploadFile,
    settings: ApiSettings,
) -> tuple[np.ndarray, ColorSpace, str | None]:
    if (
        upload.content_type is not None
        and not upload.content_type.startswith("image/")
    ):
        raise ApiRequestError(
            code="unsupported_media_type",
            message="uploaded files must use an image content type",
            status_code=415,
            details={"content_type": upload.content_type},
        )

    if (
        upload.size is not None
        and upload.size > settings.max_upload_bytes_per_file
    ):
        raise ApiRequestError(
            code="upload_too_large",
            message="uploaded image exceeds the file size limit",
            status_code=413,
            details={
                "size": upload.size,
                "maximum": settings.max_upload_bytes_per_file,
            },
        )

    upload.file.seek(0)
    raw = upload.file.read(settings.max_upload_bytes_per_file + 1)
    if len(raw) > settings.max_upload_bytes_per_file:
        raise ApiRequestError(
            code="upload_too_large",
            message="uploaded image exceeds the file size limit",
            status_code=413,
            details={
                "maximum": settings.max_upload_bytes_per_file,
            },
        )

    encoded = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ApiRequestError(
            code="invalid_image_file",
            message="uploaded file could not be decoded as an image",
        )

    pixels = int(image.shape[0]) * int(image.shape[1])
    if pixels > settings.max_image_pixels:
        raise ApiRequestError(
            code="image_pixel_limit_exceeded",
            message="decoded image exceeds the pixel limit",
            status_code=413,
            details={
                "pixels": pixels,
                "maximum": settings.max_image_pixels,
            },
        )

    if image.ndim == 2:
        color_space = ColorSpace.GRAY
    elif image.shape[2] == 3:
        color_space = ColorSpace.BGR
    elif image.shape[2] == 4:
        color_space = ColorSpace.BGRA
    else:
        raise ApiRequestError(
            code="unsupported_image_channels",
            message="decoded image must have 1, 3, or 4 channels",
            details={"shape": list(image.shape)},
        )

    return image, color_space, upload.filename


def _resolve_color_space(
    *,
    requested: ColorSpace | None,
    inferred: ColorSpace,
    array: np.ndarray,
) -> ColorSpace:
    if requested is None:
        return inferred

    allowed = {
        ColorSpace.GRAY: {ColorSpace.GRAY, ColorSpace.BINARY},
        ColorSpace.BGR: {ColorSpace.BGR},
        ColorSpace.BGRA: {ColorSpace.BGRA},
    }[inferred]

    if requested not in allowed:
        raise ApiRequestError(
            code="incompatible_color_space",
            message=(
                "requested color space does not match the decoded "
                "OpenCV channel representation"
            ),
            details={
                "requested": requested.value,
                "inferred": inferred.value,
                "shape": list(array.shape),
            },
        )

    return requested
