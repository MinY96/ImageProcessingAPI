from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from src.schemas import PipelineSpec
from src.schemas.base import BaseSchema
from src.workflow import GraphRecipeSpec


class RecipeSource(StrEnum):
    BUILTIN = "builtin"
    USER = "user"


class RecipeKind(StrEnum):
    LINEAR = "linear"
    GRAPH = "graph"


class RecipeCreateRequest(BaseSchema):
    kind: RecipeKind | None = None
    pipeline: PipelineSpec | None = None
    graph: GraphRecipeSpec | None = None
    tags: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if any(len(item) > 64 for item in normalized):
            raise ValueError("recipe tags must be 64 characters or fewer")
        return normalized

    @model_validator(mode="after")
    def validate_recipe_body(self) -> "RecipeCreateRequest":
        if (self.pipeline is None) == (self.graph is None):
            raise ValueError("provide exactly one of pipeline or graph")
        inferred = RecipeKind.GRAPH if self.graph is not None else RecipeKind.LINEAR
        if self.kind is None:
            object.__setattr__(self, "kind", inferred)
        elif self.kind != inferred:
            raise ValueError(f"kind={self.kind.value} does not match recipe body")
        return self


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
    kind: RecipeKind = RecipeKind.LINEAR
    pipeline: PipelineSpec | None = None
    graph: GraphRecipeSpec | None = None
    source: RecipeSource
    readonly: bool
    tags: list[str] = Field(default_factory=list)
    revision: int = Field(default=1, ge=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_record_body(self) -> "RecipeRecord":
        if self.kind == RecipeKind.LINEAR:
            if self.pipeline is None or self.graph is not None:
                raise ValueError("linear recipe requires pipeline only")
        else:
            if self.graph is None or self.pipeline is not None:
                raise ValueError("graph recipe requires graph only")
        artifact_name = self.pipeline.name if self.pipeline is not None else self.graph.name
        if artifact_name != self.name:
            raise ValueError("recipe name must match pipeline/graph name")
        return self


class RecipeSummary(BaseSchema):
    name: str
    kind: RecipeKind = RecipeKind.LINEAR
    display_name: str
    description: str | None = None
    version: str
    source: RecipeSource
    readonly: bool
    tags: list[str] = Field(default_factory=list)
    revision: int = Field(ge=1)
    step_count: int = Field(default=0, ge=0)
    node_count: int = Field(default=0, ge=0)
    created_at: datetime | None = None
    updated_at: datetime | None = None
