from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import Field, field_validator, model_validator

from src.schemas.base import BaseSchema


class AnnotationType(StrEnum):
    BBOX = "bbox"
    POLYGON = "polygon"
    POINT = "point"
    POLYLINE = "polyline"


class PixelPoint(BaseSchema):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class AnnotationBase(BaseSchema):
    annotation_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$",
    )
    label: str = Field(min_length=1, max_length=128)
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class BoundingBoxAnnotation(AnnotationBase):
    type: Literal[AnnotationType.BBOX] = AnnotationType.BBOX
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class PolygonAnnotation(AnnotationBase):
    type: Literal[AnnotationType.POLYGON] = AnnotationType.POLYGON
    points: list[PixelPoint] = Field(min_length=3, max_length=4096)


class PointAnnotation(AnnotationBase):
    type: Literal[AnnotationType.POINT] = AnnotationType.POINT
    point: PixelPoint


class PolylineAnnotation(AnnotationBase):
    type: Literal[AnnotationType.POLYLINE] = AnnotationType.POLYLINE
    points: list[PixelPoint] = Field(min_length=2, max_length=4096)


Annotation: TypeAlias = Annotated[
    BoundingBoxAnnotation
    | PolygonAnnotation
    | PointAnnotation
    | PolylineAnnotation,
    Field(discriminator="type"),
]


class LabelCreateRequest(BaseSchema):
    image_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$",
    )
    image_name: str = Field(min_length=1, max_length=512)
    source_uri: str | None = Field(default=None, max_length=2048)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    tags: list[str] = Field(default_factory=list, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)
    annotations: list[Annotation] = Field(default_factory=list, max_length=100_000)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if any(len(item) > 64 for item in normalized):
            raise ValueError("label tags must be 64 characters or fewer")
        return normalized


class LabelUpdateRequest(BaseSchema):
    image_name: str = Field(min_length=1, max_length=512)
    source_uri: str | None = Field(default=None, max_length=2048)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    tags: list[str] = Field(default_factory=list, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)
    annotations: list[Annotation] = Field(default_factory=list, max_length=100_000)
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if any(len(item) > 64 for item in normalized):
            raise ValueError("label tags must be 64 characters or fewer")
        return normalized


class AnnotationUpdateRequest(BaseSchema):
    annotation: Annotation
    expected_revision: int | None = Field(default=None, ge=1)


class AnnotationCreateRequest(BaseSchema):
    annotation: Annotation
    expected_revision: int | None = Field(default=None, ge=1)


class LabelDocument(BaseSchema):
    image_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    image_name: str
    source_uri: str | None = None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    annotations: list[Annotation] = Field(default_factory=list)
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_annotations(self) -> "LabelDocument":
        ids: list[str] = []
        for annotation in self.annotations:
            if annotation.annotation_id is None:
                raise ValueError("stored annotations must have annotation_id")
            ids.append(annotation.annotation_id)
            self._validate_bounds(annotation)

        if len(ids) != len(set(ids)):
            raise ValueError("annotation_id values must be unique within an image")
        return self

    def _validate_bounds(self, annotation: Annotation) -> None:
        max_x = float(self.width)
        max_y = float(self.height)

        if isinstance(annotation, BoundingBoxAnnotation):
            if annotation.x + annotation.width > max_x or annotation.y + annotation.height > max_y:
                raise ValueError(
                    f"bbox annotation is outside image bounds: {annotation.annotation_id}"
                )
            return

        if isinstance(annotation, PointAnnotation):
            points = [annotation.point]
        else:
            points = annotation.points

        for point in points:
            if point.x > max_x or point.y > max_y:
                raise ValueError(
                    f"annotation point is outside image bounds: {annotation.annotation_id}"
                )


class LabelSummary(BaseSchema):
    image_id: str
    image_name: str
    width: int
    height: int
    tags: list[str] = Field(default_factory=list)
    annotation_count: int = Field(ge=0)
    labels: list[str] = Field(default_factory=list)
    revision: int = Field(ge=1)
    updated_at: datetime


class LabelListResponse(BaseSchema):
    items: list[LabelSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class LabelClassSummary(BaseSchema):
    label: str
    annotation_count: int = Field(ge=1)
    image_count: int = Field(ge=1)
