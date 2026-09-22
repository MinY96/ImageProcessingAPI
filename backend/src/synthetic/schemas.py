from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from src.schemas.base import BaseSchema


class SyntheticMethod(StrEnum):
    PROCEDURAL = "procedural"
    CUT_PASTE = "cut_paste"
    ALPHA_BLEND = "alpha_blend"
    SEAMLESS_CLONE = "seamless_clone"
    ASSET_COMPOSITE = "asset_composite"
    DIFFUSION_INPAINT = "diffusion_inpaint"


class SyntheticMaskType(StrEnum):
    MANUAL = "manual"
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    RANDOM_BLOB = "random_blob"
    PERLIN = "perlin"
    CRACK = "crack"


class ProceduralPattern(StrEnum):
    BLOB = "blob"
    STAIN = "stain"
    DROPLET = "droplet"
    POOLING = "pooling"
    CRACK = "crack"
    SPECK = "speck"
    TEXTURE = "texture"


class SyntheticMaskSpec(BaseSchema):
    type: SyntheticMaskType = SyntheticMaskType.RANDOM_BLOB
    center_x: float = Field(default=0.5, ge=0.0, le=1.0)
    center_y: float = Field(default=0.5, ge=0.0, le=1.0)
    width_ratio: float = Field(default=0.18, gt=0.0, le=1.0)
    height_ratio: float = Field(default=0.18, gt=0.0, le=1.0)
    rotation_deg: float = Field(default=0.0, ge=-360.0, le=360.0)
    polygon: list[tuple[float, float]] = Field(default_factory=list, max_length=128)
    feather_px: int = Field(default=3, ge=0, le=128)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, value: list[tuple[float, float]]) -> list[tuple[float, float]]:
        for x, y in value:
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError("polygon coordinates must be normalized to 0..1")
        return value

    @model_validator(mode="after")
    def validate_polygon_requirement(self) -> "SyntheticMaskSpec":
        if self.type == SyntheticMaskType.POLYGON and len(self.polygon) < 3:
            raise ValueError("polygon mask requires at least three points")
        return self


class SyntheticGenerateRequest(BaseSchema):
    method: SyntheticMethod
    defect_type: str = Field(default="anomaly", min_length=1, max_length=128)
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    count: int = Field(default=1, ge=1, le=16)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    mask: SyntheticMaskSpec | None = None
    asset_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_.-]{1,128}$")
    parameters: dict[str, Any] = Field(default_factory=dict)


class SyntheticMethodInfo(BaseSchema):
    method: SyntheticMethod
    display_name: str
    description: str
    requires_asset: bool = False
    supports_asset: bool = False
    supports_uploaded_mask: bool = True
    supports_generated_mask: bool = True
    optional_dependencies: list[str] = Field(default_factory=list)


class SyntheticAssetCreateRequest(BaseSchema):
    asset_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_.-]{1,128}$")
    name: str = Field(min_length=1, max_length=256)
    category: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class SyntheticAssetSummary(BaseSchema):
    asset_id: str
    name: str
    category: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    has_mask: bool
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiffusionModelStatus(BaseSchema):
    model: str
    display_name: str
    provider: str
    model_id: str
    dependency_available: bool
    loaded: bool
    local_files_only: bool
    cache_dir: str | None = None
    device: str
    notes: str | None = None


class SyntheticQualityMetrics(BaseSchema):
    changed_area_ratio: float = Field(ge=0.0, le=1.0)
    outside_mask_mean_abs_diff: float = Field(ge=0.0)
    outside_mask_max_abs_diff: float = Field(ge=0.0)
    inside_mask_mean_abs_diff: float = Field(ge=0.0)


class SyntheticCandidateMetadata(BaseSchema):
    index: int = Field(ge=0)
    seed: int = Field(ge=0)
    method: SyntheticMethod
    defect_type: str
    severity: float = Field(ge=0.0, le=1.0)
    generator_metadata: dict[str, Any] = Field(default_factory=dict)
    quality: SyntheticQualityMetrics | None = None
