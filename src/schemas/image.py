# src/schemas/image.py

from __future__ import annotations

import numpy as np

from pydantic import (
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from .base import BaseSchema
from .enums import ColorSpace, ImageDType

class ImageData(BaseSchema):

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
    )

    data: np.ndarray = Field(
        repr=False,
        exclude=True,
    )

    color_space: ColorSpace

    name: str | None = None

    @field_validator("data")
    @classmethod
    def validate_array(
        cls,
        value: np.ndarray,
    ) -> np.ndarray:

        if not isinstance(value, np.ndarray):
            raise TypeError(
                "data must be a numpy.ndarray"
            )

        if value.size == 0:
            raise ValueError(
                "image must not be empty"
            )

        if value.ndim not in (2, 3):
            raise ValueError(
                "image ndim must be 2 or 3"
            )

        supported = {
            dtype.value
            for dtype in ImageDType
        }

        if value.dtype.name not in supported:
            raise ValueError(
                f"unsupported image dtype: "
                f"{value.dtype.name}"
            )

        return value

    @model_validator(mode="after")
    def validate_color_space_channels(
        self,
    ) -> "ImageData":

        channels = (
            1
            if self.data.ndim == 2
            else self.data.shape[2]
        )

        expected_channels = {
            ColorSpace.GRAY: 1,
            ColorSpace.BINARY: 1,

            ColorSpace.BGR: 3,
            ColorSpace.RGB: 3,
            ColorSpace.HSV: 3,
            ColorSpace.LAB: 3,

            ColorSpace.BGRA: 4,
            ColorSpace.RGBA: 4,
        }

        expected = expected_channels.get(
            self.color_space
        )

        if (
            expected is not None
            and channels != expected
        ):
            raise ValueError(
                f"color_space="
                f"{self.color_space.value} "
                f"requires {expected} channel(s), "
                f"got {channels}"
            )

        return self

    @computed_field
    @property
    def width(self) -> int:
        return int(self.data.shape[1])

    @computed_field
    @property
    def height(self) -> int:
        return int(self.data.shape[0])

    @computed_field
    @property
    def channels(self) -> int:
        if self.data.ndim == 2:
            return 1

        return int(
            self.data.shape[2]
        )

    @computed_field
    @property
    def dtype(self) -> str:
        return self.data.dtype.name

    @computed_field
    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(
            int(value)
            for value in self.data.shape
        )

class ImageConstraint(BaseSchema):

    allowed_color_spaces: list[
        ColorSpace
    ] = Field(
        default_factory=list
    )

    allowed_dtypes: list[
        ImageDType
    ] = Field(
        default_factory=list
    )

    min_width: int | None = Field(
        default=None,
        ge=1,
    )

    max_width: int | None = Field(
        default=None,
        ge=1,
    )

    min_height: int | None = Field(
        default=None,
        ge=1,
    )

    max_height: int | None = Field(
        default=None,
        ge=1,
    )

    @model_validator(mode="after")
    def validate_dimensions(
        self,
    ) -> "ImageConstraint":

        if (
            self.min_width is not None
            and self.max_width is not None
            and self.min_width > self.max_width
        ):
            raise ValueError(
                "min_width must be <= max_width"
            )

        if (
            self.min_height is not None
            and self.max_height is not None
            and self.min_height > self.max_height
        ):
            raise ValueError(
                "min_height must be <= max_height"
            )

        return self
