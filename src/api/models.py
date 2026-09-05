from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from src.schemas import ColorSpace, PipelineSpec
from src.schemas.base import BaseSchema


class ResponseFormat(StrEnum):
    JSON = "json"
    ZIP = "zip"


class ImageUploadBinding(BaseSchema):
    input_name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )
    file_index: int = Field(ge=0)
    color_space: ColorSpace | None = None
    name: str | None = None


class ModelInputBinding(BaseSchema):
    input_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    model_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")


class InputPayloadBase(BaseSchema):
    inputs: dict[str, Any] = Field(default_factory=dict)
    image_inputs: list[ImageUploadBinding] = Field(
        default_factory=list
    )
    model_inputs: list[ModelInputBinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_input_bindings(self) -> "InputPayloadBase":
        image_names = [item.input_name for item in self.image_inputs]
        model_names = [item.input_name for item in self.model_inputs]

        if len(image_names) != len(set(image_names)):
            raise ValueError(
                "image input names must be unique"
            )

        if len(model_names) != len(set(model_names)):
            raise ValueError("model input names must be unique")

        conflicts = (
            (set(image_names) & set(model_names))
            | (set(image_names) & set(self.inputs))
            | (set(model_names) & set(self.inputs))
        )
        if conflicts:
            raise ValueError(
                "inputs, image_inputs, and model_inputs contain the same names: "
                f"{sorted(conflicts)}"
            )

        return self


class OperationRunPayload(InputPayloadBase):
    params: dict[str, Any] = Field(default_factory=dict)


class PipelineRunPayload(InputPayloadBase):
    retain_intermediates: bool = False


class AdHocPipelineRunPayload(PipelineRunPayload):
    pipeline: PipelineSpec


class PipelineValidationResponse(BaseSchema):
    valid: bool
    pipeline: str
    registry_revision: int | None = None
    output_names: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
