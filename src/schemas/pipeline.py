from __future__ import annotations

import re
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import Field, field_validator, model_validator

from .base import BaseSchema
from .enums import PipelineReferenceType
from .operation import InputSlotSpec
from .result import (
    ExecutionMetadata,
    OperationError,
    OperationOutput,
)


class PipelineInputReference(BaseSchema):
    type: Literal[
        PipelineReferenceType.PIPELINE_INPUT
    ] = PipelineReferenceType.PIPELINE_INPUT

    input_name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )


class StepOutputReference(BaseSchema):
    type: Literal[
        PipelineReferenceType.STEP_OUTPUT
    ] = PipelineReferenceType.STEP_OUTPUT

    step_id: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )
    output_name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )


PipelineValueReference: TypeAlias = Annotated[
    PipelineInputReference | StepOutputReference,
    Field(discriminator="type"),
]


class PipelineStepSpec(BaseSchema):
    id: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )
    operation: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )
    inputs: dict[
        str,
        PipelineValueReference,
    ] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("inputs")
    @classmethod
    def validate_input_binding_names(
        cls,
        value: dict[str, PipelineValueReference],
    ) -> dict[str, PipelineValueReference]:
        pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        invalid = [
            name
            for name in value
            if not pattern.fullmatch(name)
        ]

        if invalid:
            raise ValueError(
                f"invalid input binding names: {invalid}"
            )

        return value


class PipelineSpec(BaseSchema):
    name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )
    display_name: str
    description: str | None = None
    version: str = "1.0.0"

    inputs: list[InputSlotSpec] = Field(
        default_factory=list
    )
    steps: list[PipelineStepSpec] = Field(
        min_length=1,
        max_length=100,
    )
    outputs: dict[
        str,
        PipelineValueReference,
    ] = Field(default_factory=dict)

    @field_validator("outputs")
    @classmethod
    def validate_output_names(
        cls,
        value: dict[str, PipelineValueReference],
    ) -> dict[str, PipelineValueReference]:
        pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        invalid = [
            name
            for name in value
            if not pattern.fullmatch(name)
        ]

        if invalid:
            raise ValueError(
                f"invalid pipeline output names: {invalid}"
            )

        return value

    @model_validator(mode="after")
    def validate_references(self) -> "PipelineSpec":
        input_names = [item.name for item in self.inputs]
        if len(input_names) != len(set(input_names)):
            raise ValueError(
                "pipeline input names must be unique"
            )

        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("pipeline step ids must be unique")

        known_inputs = set(input_names)
        previous_steps: set[str] = set()

        for step in self.steps:
            for reference in step.inputs.values():
                self._validate_reference(
                    reference=reference,
                    known_inputs=known_inputs,
                    allowed_steps=previous_steps,
                    location=f"step {step.id}",
                )

            previous_steps.add(step.id)

        all_steps = set(step_ids)
        for output_name, reference in self.outputs.items():
            self._validate_reference(
                reference=reference,
                known_inputs=known_inputs,
                allowed_steps=all_steps,
                location=f"pipeline output {output_name}",
            )

        return self

    @staticmethod
    def _validate_reference(
        *,
        reference: PipelineValueReference,
        known_inputs: set[str],
        allowed_steps: set[str],
        location: str,
    ) -> None:
        if isinstance(reference, PipelineInputReference):
            if reference.input_name not in known_inputs:
                raise ValueError(
                    f"{location} references unknown pipeline input: "
                    f"{reference.input_name}"
                )
            return

        if reference.step_id not in allowed_steps:
            raise ValueError(
                f"{location} references unavailable step: "
                f"{reference.step_id}"
            )


class PipelineStepExecution(BaseSchema):
    step_id: str
    operation: str
    success: bool
    metadata: ExecutionMetadata
    error: OperationError | None = None

    @model_validator(mode="after")
    def validate_success_error(
        self,
    ) -> "PipelineStepExecution":
        if self.success and self.error is not None:
            raise ValueError(
                "successful step must not contain error"
            )
        if not self.success and self.error is None:
            raise ValueError(
                "failed step must contain error"
            )
        return self


class PipelineError(BaseSchema):
    code: str
    message: str
    step_id: str | None = None
    operation: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PipelineExecutionResult(BaseSchema):
    pipeline: str
    success: bool
    output: OperationOutput = Field(
        default_factory=OperationOutput
    )
    steps: list[PipelineStepExecution] = Field(
        default_factory=list
    )
    intermediates: dict[str, OperationOutput] = Field(
        default_factory=dict
    )
    metadata: ExecutionMetadata
    error: PipelineError | None = None

    @model_validator(mode="after")
    def validate_success_error(
        self,
    ) -> "PipelineExecutionResult":
        if self.success and self.error is not None:
            raise ValueError(
                "successful pipeline must not contain error"
            )
        if not self.success and self.error is None:
            raise ValueError(
                "failed pipeline must contain error"
            )
        return self
