# src/schemas/parameter.py

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from .base import BaseSchema
from .enums import ParameterType


ScalarValue: TypeAlias = str | int | float | bool


class ParameterBase(BaseSchema):
    title: str

    description: str | None = None

    required: bool = False

    unit: str | None = None

    order: int = Field(
        default=0,
        ge=0,
    )

class ContinuousParameterSpec(ParameterBase):
    type: Literal[
        ParameterType.CONTINUOUS
    ] = ParameterType.CONTINUOUS

    min_value: float
    max_value: float

    default: float | None = None

    step: float | None = Field(
        default=None,
        gt=0,
    )

    @model_validator(mode="after")
    def validate_range(self) -> "ContinuousParameterSpec":

        if self.min_value >= self.max_value:
            raise ValueError(
                "min_value must be smaller than max_value"
            )

        if (
            self.default is not None
            and not self.min_value
            <= self.default
            <= self.max_value
        ):
            raise ValueError(
                "default must be within "
                "[min_value, max_value]"
            )

        return self

class DiscreteParameterSpec(ParameterBase):
    type: Literal[
        ParameterType.DISCRETE
    ] = ParameterType.DISCRETE

    min_value: int | None = None
    max_value: int | None = None

    step: int | None = Field(
        default=None,
        gt=0,
    )

    values: list[int] | None = None

    default: int | None = None

    @model_validator(mode="after")
    def validate_discrete(
        self,
    ) -> "DiscreteParameterSpec":

        uses_values = self.values is not None

        uses_range = (
            self.min_value is not None
            or self.max_value is not None
            or self.step is not None
        )

        # 둘을 동시에 사용할 수 없음
        if uses_values and uses_range:
            raise ValueError(
                "use either values or "
                "min_value/max_value/step, not both"
            )

        if not uses_values and not uses_range:
            raise ValueError(
                "define values or "
                "min_value/max_value/step"
            )

        # ---------------------------------
        # explicit values
        # ---------------------------------

        if uses_values:

            assert self.values is not None

            if not self.values:
                raise ValueError(
                    "values must not be empty"
                )

            if len(self.values) != len(set(self.values)):
                raise ValueError(
                    "values must not contain duplicates"
                )

            if (
                self.default is not None
                and self.default not in self.values
            ):
                raise ValueError(
                    "default must be one of values"
                )

            return self

        # ---------------------------------
        # range
        # ---------------------------------

        if (
            self.min_value is None
            or self.max_value is None
        ):
            raise ValueError(
                "min_value and max_value "
                "are required for range mode"
            )

        if self.min_value > self.max_value:
            raise ValueError(
                "min_value must be <= max_value"
            )

        step = self.step or 1

        if self.default is not None:

            if not (
                self.min_value
                <= self.default
                <= self.max_value
            ):
                raise ValueError(
                    "default must be within range"
                )

            if (
                self.default - self.min_value
            ) % step != 0:
                raise ValueError(
                    "default must align with step"
                )

        return self

class CategoryChoice(BaseSchema):
    value: ScalarValue
    label: str

    description: str | None = None

class CategoryParameterSpec(ParameterBase):
    type: Literal[
        ParameterType.CATEGORY
    ] = ParameterType.CATEGORY

    choices: list[CategoryChoice]

    default: ScalarValue | None = None

    @model_validator(mode="after")
    def validate_choices(
        self,
    ) -> "CategoryParameterSpec":

        if not self.choices:
            raise ValueError(
                "choices must not be empty"
            )

        keys = [
            (
                type(choice.value).__name__,
                repr(choice.value),
            )
            for choice in self.choices
        ]

        if len(keys) != len(set(keys)):
            raise ValueError(
                "choice values must be unique"
            )

        if self.default is not None:

            valid = any(
                type(choice.value)
                is type(self.default)
                and choice.value == self.default
                for choice in self.choices
            )

            if not valid:
                raise ValueError(
                    "default must be one of choices"
                )

        return self

ParameterSpec: TypeAlias = Annotated[
    ContinuousParameterSpec
    | DiscreteParameterSpec
    | CategoryParameterSpec,
    Field(discriminator="type"),
]
