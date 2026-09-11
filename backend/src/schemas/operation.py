# src/schemas/operation.py

from __future__ import annotations

import re

from pydantic import Field, field_validator, model_validator

from .base import BaseSchema
from .enums import (
    InputKind,
    OperationCategory,
    OutputKind,
)
from .image import ImageConstraint
from .parameter import ParameterSpec
from .constraint import ConstraintSpec

class InputSlotSpec(BaseSchema):

    name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )

    kind: InputKind

    required: bool = True

    description: str | None = None

    image_constraint: (
        ImageConstraint | None
    ) = None

    @model_validator(mode="after")
    def validate_constraint(
        self,
    ) -> "InputSlotSpec":

        image_kinds = {
            InputKind.IMAGE,
            InputKind.MASK,
            InputKind.TEMPLATE,
        }

        if (
            self.image_constraint is not None
            and self.kind not in image_kinds
        ):
            raise ValueError(
                "image_constraint is only valid "
                "for image-like inputs"
            )

        return self

class OutputSlotSpec(BaseSchema):

    name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )

    kind: OutputKind

    description: str | None = None

class OperationSpec(BaseSchema):

    name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )

    display_name: str

    category: OperationCategory

    description: str | None = None

    version: str = "1.0.0"

    inputs: list[
        InputSlotSpec
    ]

    parameters: dict[
        str,
        ParameterSpec,
    ] = Field(
        default_factory=dict
    )

    outputs: list[
        OutputSlotSpec
    ]

    constraints: list[
        ConstraintSpec
    ] = Field(
        default_factory=list
    )

    @field_validator("parameters")
    @classmethod
    def validate_parameter_names(
        cls,
        value: dict[str, ParameterSpec],
    ) -> dict[str, ParameterSpec]:

        pattern = re.compile(
            r"^[a-z][a-z0-9_]*$"
        )

        invalid = [
            name
            for name in value
            if not pattern.fullmatch(name)
        ]

        if invalid:
            raise ValueError(
                f"invalid parameter names: "
                f"{invalid}"
            )

        return value

    @model_validator(mode="after")
    def validate_slot_names(
        self,
    ) -> "OperationSpec":

        input_names = [
            item.name
            for item in self.inputs
        ]

        output_names = [
            item.name
            for item in self.outputs
        ]

        if len(input_names) != len(
            set(input_names)
        ):
            raise ValueError(
                "input slot names must be unique"
            )

        if len(output_names) != len(
            set(output_names)
        ):
            raise ValueError(
                "output slot names must be unique"
            )

        return self

    @model_validator(mode="after")
    def validate_constraints(
        self,
    ) -> "OperationSpec":

        parameter_names = set(
            self.parameters.keys()
        )

        for constraint in self.constraints:
            unknown = (
                constraint.referenced_parameters()
                - parameter_names
            )

            if unknown:
                raise ValueError(
                    "constraint references unknown "
                    f"parameters: {sorted(unknown)}"
                )

        return self
