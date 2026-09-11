from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from src.schemas.base import BaseSchema


class ModelSpec(BaseSchema):
    model_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    algorithm: str
    feature_schema: str
    labels: dict[int, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelData(BaseSchema):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
    )

    spec: ModelSpec
    model: Any = Field(repr=False, exclude=True)


class PredictionData(BaseSchema):
    labels: list[int | float]
    label_names: list[str | None] = Field(default_factory=list)
    model_id: str
    model_version: str
    algorithm: str
    details: dict[str, Any] = Field(default_factory=dict)
