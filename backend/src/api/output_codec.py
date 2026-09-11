from __future__ import annotations

import base64
import io
import json
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.analysis import AnalysisOptions, ImageAnalyzer
from src.schemas import (
    ColorSpace,
    ExecutionResult,
    ImageData,
    OperationOutput,
    PipelineExecutionResult,
)
from src.workflow import WorkflowExecutionResult

from .config import ApiSettings
from .errors import ApiRequestError
from .models import ResponseFormat


@dataclass(frozen=True, slots=True)
class EncodedArtifact:
    path: str
    content: bytes
    metadata: dict[str, Any]


def render_operation_result(
    *,
    result: ExecutionResult,
    response_format: ResponseFormat,
    settings: ApiSettings,
    analyzer: ImageAnalyzer | None = None,
    analysis_options: AnalysisOptions | None = None,
):
    payload: dict[str, Any] = {
        "operation": result.operation,
        "success": result.success,
        "metadata": result.metadata.model_dump(mode="json"),
        "error": (
            result.error.model_dump(mode="json")
            if result.error is not None
            else None
        ),
    }

    if not result.success:
        payload["output"] = {"images": {}, "data": {}}
        return JSONResponse(
            status_code=_operation_status_code(result),
            content=payload,
        )

    artifacts: list[EncodedArtifact] = []
    payload["output"] = _encode_output(
        output=result.output,
        prefix="output",
        response_format=response_format,
        settings=settings,
        artifacts=artifacts,
        analyzer=analyzer,
        analysis_options=analysis_options,
    )
    return _render_success_payload(
        payload=payload,
        artifacts=artifacts,
        response_format=response_format,
        settings=settings,
        download_name=f"{result.operation}_result.zip",
    )


def render_pipeline_result(
    *,
    result: PipelineExecutionResult,
    response_format: ResponseFormat,
    settings: ApiSettings,
    analyzer: ImageAnalyzer | None = None,
    analysis_options: AnalysisOptions | None = None,
    analyze_intermediates: bool = False,
):
    payload: dict[str, Any] = {
        "pipeline": result.pipeline,
        "success": result.success,
        "steps": [
            item.model_dump(mode="json")
            for item in result.steps
        ],
        "metadata": result.metadata.model_dump(mode="json"),
        "error": (
            result.error.model_dump(mode="json")
            if result.error is not None
            else None
        ),
    }

    if not result.success:
        payload["output"] = {"images": {}, "data": {}}
        payload["intermediates"] = {}
        return JSONResponse(
            status_code=_pipeline_status_code(result),
            content=payload,
        )

    artifacts: list[EncodedArtifact] = []
    payload["output"] = _encode_output(
        output=result.output,
        prefix="output",
        response_format=response_format,
        settings=settings,
        artifacts=artifacts,
        analyzer=analyzer,
        analysis_options=analysis_options,
    )
    payload["intermediates"] = {
        step_id: _encode_output(
            output=output,
            prefix=f"intermediates/{step_id}",
            response_format=response_format,
            settings=settings,
            artifacts=artifacts,
            analyzer=(analyzer if analyze_intermediates else None),
            analysis_options=(analysis_options if analyze_intermediates else None),
        )
        for step_id, output in result.intermediates.items()
    }

    return _render_success_payload(
        payload=payload,
        artifacts=artifacts,
        response_format=response_format,
        settings=settings,
        download_name=f"{result.pipeline}_result.zip",
    )



def render_workflow_result(
    *,
    result: WorkflowExecutionResult,
    response_format: ResponseFormat,
    settings: ApiSettings,
    analyzer: ImageAnalyzer | None = None,
    analysis_options: AnalysisOptions | None = None,
    analyze_intermediates: bool = False,
):
    payload: dict[str, Any] = {
        "recipe": result.recipe,
        "success": result.success,
        "nodes": [item.model_dump(mode="json") for item in result.nodes],
        "metadata": result.metadata.model_dump(mode="json"),
        "error": (result.error.model_dump(mode="json") if result.error is not None else None),
    }
    if not result.success:
        payload["output"] = {"images": {}, "data": {}}
        payload["intermediates"] = {}
        return JSONResponse(status_code=422 if result.error and "validation" in result.error.code else 400, content=payload)

    artifacts: list[EncodedArtifact] = []
    payload["output"] = _encode_output(
        output=result.output, prefix="output", response_format=response_format, settings=settings,
        artifacts=artifacts, analyzer=analyzer, analysis_options=analysis_options,
    )
    payload["intermediates"] = {
        node_id: _encode_output(
            output=output, prefix=f"intermediates/{node_id}", response_format=response_format,
            settings=settings, artifacts=artifacts,
            analyzer=(analyzer if analyze_intermediates else None),
            analysis_options=(analysis_options if analyze_intermediates else None),
        )
        for node_id, output in result.intermediates.items()
    }
    return _render_success_payload(
        payload=payload, artifacts=artifacts, response_format=response_format, settings=settings,
        download_name=f"{result.recipe}_result.zip",
    )

def _encode_output(
    *,
    output: OperationOutput,
    prefix: str,
    response_format: ResponseFormat,
    settings: ApiSettings,
    artifacts: list[EncodedArtifact],
    analyzer: ImageAnalyzer | None = None,
    analysis_options: AnalysisOptions | None = None,
) -> dict[str, Any]:
    images = {}

    for name, image in output.images.items():
        artifact = _encode_image(
            image=image,
            path_prefix=prefix,
            output_name=name,
        )
        artifacts.append(artifact)

        metadata = dict(artifact.metadata)
        if response_format == ResponseFormat.JSON:
            metadata.update(
                {
                    "encoding": "base64",
                    "data": base64.b64encode(
                        artifact.content
                    ).decode("ascii"),
                }
            )
        else:
            metadata["file"] = artifact.path

        if analyzer is not None and analysis_options is not None:
            metadata["analysis"] = analyzer.analyze(
                image,
                options=analysis_options,
            ).model_dump(mode="json")

        images[name] = metadata

    return {
        "images": images,
        "data": _normalize_data(
            output.data,
            max_array_items=settings.max_inline_array_items,
        ),
    }


def _encode_image(
    *,
    image: ImageData,
    path_prefix: str,
    output_name: str,
) -> EncodedArtifact:
    png_ready = image.data.dtype in {
        np.dtype(np.uint8),
        np.dtype(np.uint16),
    } and image.color_space in {
        ColorSpace.GRAY,
        ColorSpace.BINARY,
        ColorSpace.BGR,
        ColorSpace.BGRA,
        ColorSpace.RGB,
        ColorSpace.RGBA,
    }

    if png_ready:
        array = image.data
        if image.color_space == ColorSpace.RGB:
            array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
        elif image.color_space == ColorSpace.RGBA:
            array = cv2.cvtColor(array, cv2.COLOR_RGBA2BGRA)

        success, encoded = cv2.imencode(".png", array)
        if not success:
            raise ApiRequestError(
                code="output_encoding_failed",
                message="OpenCV could not encode an output image",
                status_code=500,
                details={"output": output_name},
            )
        content = encoded.tobytes()
        extension = "png"
        media_type = "image/png"
    else:
        buffer = io.BytesIO()
        np.save(buffer, image.data, allow_pickle=False)
        content = buffer.getvalue()
        extension = "npy"
        media_type = "application/x-npy"

    path = f"{path_prefix}/{output_name}.{extension}"
    return EncodedArtifact(
        path=path,
        content=content,
        metadata={
            "media_type": media_type,
            "size_bytes": len(content),
            "width": image.width,
            "height": image.height,
            "channels": image.channels,
            "dtype": image.dtype,
            "color_space": image.color_space.value,
            "shape": list(image.shape),
            "name": image.name,
        },
    )


def _normalize_data(
    value: Any,
    *,
    max_array_items: int,
) -> Any:
    if isinstance(value, np.ndarray):
        if value.size > max_array_items:
            raise ApiRequestError(
                code="data_output_too_large",
                message=(
                    "non-image ndarray output is too large for inline JSON"
                ),
                status_code=413,
                details={
                    "items": int(value.size),
                    "maximum": max_array_items,
                },
            )
        return value.tolist()

    if isinstance(value, np.generic):
        return value.item()

    if isinstance(value, BaseModel):
        return _normalize_data(
            value.model_dump(mode="python"),
            max_array_items=max_array_items,
        )

    if isinstance(value, dict):
        return {
            str(key): _normalize_data(
                item,
                max_array_items=max_array_items,
            )
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _normalize_data(
                item,
                max_array_items=max_array_items,
            )
            for item in value
        ]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    raise ApiRequestError(
        code="unsupported_output_type",
        message="output data contains a non-serializable value",
        status_code=500,
        details={"type": type(value).__name__},
    )


def _render_success_payload(
    *,
    payload: dict[str, Any],
    artifacts: list[EncodedArtifact],
    response_format: ResponseFormat,
    settings: ApiSettings,
    download_name: str,
):
    total_bytes = sum(len(item.content) for item in artifacts)
    maximum = (
        settings.max_json_binary_bytes
        if response_format == ResponseFormat.JSON
        else settings.max_zip_binary_bytes
    )
    if total_bytes > maximum:
        raise ApiRequestError(
            code="response_size_limit_exceeded",
            message="encoded outputs exceed the response size limit",
            status_code=413,
            details={
                "encoded_bytes": total_bytes,
                "maximum": maximum,
                "response_format": response_format.value,
            },
        )

    if response_format == ResponseFormat.JSON:
        return JSONResponse(content=payload)

    return _build_zip_response(
        payload=payload,
        artifacts=artifacts,
        download_name=download_name,
    )


def _build_zip_response(
    *,
    payload: dict[str, Any],
    artifacts: list[EncodedArtifact],
    download_name: str,
) -> StreamingResponse:
    spool = tempfile.SpooledTemporaryFile(
        max_size=8 * 1024 * 1024,
        mode="w+b",
    )

    with zipfile.ZipFile(
        spool,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
        )
        for artifact in artifacts:
            archive.writestr(artifact.path, artifact.content)

    spool.seek(0)

    def iterator():
        try:
            while chunk := spool.read(1024 * 1024):
                yield chunk
        finally:
            spool.close()

    return StreamingResponse(
        iterator(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{download_name}"'
            )
        },
    )


def _operation_status_code(result: ExecutionResult) -> int:
    assert result.error is not None
    return {
        "operation_not_found": 404,
        "input_validation_error": 422,
        "parameter_validation_error": 422,
        "resource_limit_exceeded": 413,
        "invalid_output_size": 422,
        "invalid_parameter_combination": 422,
        "invalid_rectangle": 422,
        "invalid_points": 422,
        "invalid_channel": 422,
        "invalid_kernel": 422,
        "incompatible_inputs": 422,
        "invalid_template_size": 422,
        "unsupported_color_space": 422,
        "handler_execution_error": 500,
        "invalid_handler_output": 500,
        "output_validation_error": 500,
    }.get(result.error.code, 400)


def _pipeline_status_code(result: PipelineExecutionResult) -> int:
    assert result.error is not None

    if result.error.code in {
        "pipeline_validation_error",
        "pipeline_input_validation_error",
    }:
        return 422

    if result.error.code == "pipeline_step_failed":
        cause = result.error.details.get("cause", {})
        return {
            "resource_limit_exceeded": 413,
            "input_validation_error": 422,
            "parameter_validation_error": 422,
            "invalid_output_size": 422,
            "invalid_parameter_combination": 422,
            "invalid_rectangle": 422,
            "invalid_points": 422,
            "invalid_channel": 422,
            "invalid_kernel": 422,
            "incompatible_inputs": 422,
            "invalid_template_size": 422,
            "unsupported_color_space": 422,
            "handler_execution_error": 500,
            "invalid_handler_output": 500,
            "output_validation_error": 500,
        }.get(cause.get("code"), 400)

    return 400
