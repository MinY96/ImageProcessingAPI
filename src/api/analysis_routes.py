from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.analysis import ImageAnalysisPayload, ImageAnalysisResult

from .input_codec import decode_upload_image, parse_form_payload
from .services import ApiServices


def create_analysis_router(prefix: str, get_services) -> APIRouter:
    router = APIRouter(prefix=f"{prefix}/analysis", tags=["analysis"])

    @router.post("/image", response_model=ImageAnalysisResult)
    def analyze_image(
        payload: Annotated[
            str,
            Form(
                description=(
                    "ImageAnalysisPayload JSON string. Example: "
                    "{\"options\": {\"include_hsv_histogram\": true}}"
                )
            ),
        ],
        file: Annotated[UploadFile, File()],
        services: Annotated[ApiServices, Depends(get_services)],
    ):
        parsed = parse_form_payload(payload, ImageAnalysisPayload)
        image = decode_upload_image(
            upload=file,
            settings=services.settings,
            color_space=parsed.color_space,
            name=parsed.name,
        )
        source_size = file.size
        if source_size is None:
            current = file.file.tell()
            file.file.seek(0, 2)
            source_size = file.file.tell()
            file.file.seek(current)

        return services.image_analyzer.analyze(
            image,
            options=parsed.options,
            source_size_bytes=int(source_size),
        )

    return router
