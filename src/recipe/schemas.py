from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from src.schemas import PipelineSpec
from src.schemas.base import BaseSchema


class RecipeSource(StrEnum):
    BUILTIN = "builtin"
    USER = "user"


class RecipeCreateRequest(BaseSchema):
    pipeline: PipelineSpec
    tags: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if any(len(item) > 64 for item in normalized):
            raise ValueError("recipe tags must be 64 characters or fewer")
        return normalized


class RecipeUpdateRequest(RecipeCreateRequest):
    expected_revision: int | None = Field(default=None, ge=1)


class RecipeCloneRequest(BaseSchema):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    tags: list[str] | None = Field(default=None, max_length=32)

    @field_validator("tags")
    @classmethod
    def normalize_clone_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = sorted({item.strip() for item in value if item.strip()})
        if any(len(item) > 64 for item in normalized):
            raise ValueError("recipe tags must be 64 characters or fewer")
        return normalized


class RecipeRecord(BaseSchema):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    pipeline: PipelineSpec
    source: RecipeSource
    readonly: bool
    tags: list[str] = Field(default_factory=list)
    revision: int = Field(default=1, ge=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecipeSummary(BaseSchema):
    name: str
    display_name: str
    description: str | None = None
    version: str
    source: RecipeSource
    readonly: bool
    tags: list[str] = Field(default_factory=list)
    revision: int = Field(ge=1)
    step_count: int = Field(ge=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None
