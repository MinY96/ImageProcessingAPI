# src/schemas/result.py

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, model_validator

from .base import BaseSchema
from .image import ImageData

class OperationError(BaseSchema):

    code: str

    message: str

    details: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

class ExecutionMetadata(BaseSchema):

    duration_ms: float = Field(
        ge=0
    )

    warnings: list[str] = Field(
        default_factory=list
    )

class OperationOutput(BaseSchema):

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    images: dict[
        str,
        ImageData,
    ] = Field(
        default_factory=dict
    )

    data: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

class ExecutionResult(BaseSchema):

    operation: str

    success: bool

    output: OperationOutput = Field(
        default_factory=OperationOutput
    )

    metadata: ExecutionMetadata

    error: OperationError | None = None

    @model_validator(mode="after")
    def validate_success_error(
        self,
    ) -> "ExecutionResult":

        if (
            self.success
            and self.error is not None
        ):
            raise ValueError(
                "successful result must "
                "not contain error"
            )

        if (
            not self.success
            and self.error is None
        ):
            raise ValueError(
                "failed result must "
                "contain error"
            )

        return self
