from __future__ import annotations

from pydantic import Field, field_validator

from src.schemas import ColorSpace
from src.schemas.base import BaseSchema


class AnalysisOptions(BaseSchema):
    """Controls the amount of image analysis returned to a client."""

    histogram_bins: int = Field(default=256, ge=16, le=1024)
    include_gray_histogram: bool = True
    include_rgb_histogram: bool = True
    include_hsv_histogram: bool = True
    include_channel_statistics: bool = True
    include_features: bool = True
    include_profiles: bool = True
    include_profile_derivative: bool = True
    profile_max_points: int = Field(default=4096, ge=64, le=32768)
    profile_smoothing_window: int = Field(default=1, ge=1, le=101)
    statistics_sample_max_pixels: int = Field(default=2_000_000, ge=10_000, le=64_000_000)
    feature_max_pixels: int = Field(default=2_000_000, ge=10_000, le=64_000_000)
    derived_color_max_pixels: int = Field(default=4_000_000, ge=10_000, le=64_000_000)

    @field_validator("profile_smoothing_window")
    @classmethod
    def validate_smoothing_window(cls, value: int) -> int:
        if value % 2 == 0:
            raise ValueError("profile_smoothing_window must be odd")
        return value


class ImageAnalysisPayload(BaseSchema):
    color_space: ColorSpace | None = None
    name: str | None = None
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class AnalysisImageMetadata(BaseSchema):
    name: str | None = None
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    channels: int = Field(ge=1)
    pixel_count: int = Field(ge=1)
    dtype: str
    bit_depth_per_channel: int = Field(ge=1)
    bits_per_pixel: int = Field(ge=1)
    color_space: ColorSpace
    shape: list[int]
    aspect_ratio: float = Field(gt=0)
    decoded_size_bytes: int = Field(ge=1)
    source_size_bytes: int | None = Field(default=None, ge=0)


class NumericStatistics(BaseSchema):
    total_count: int = Field(ge=1)
    sample_count: int = Field(ge=1)
    quantiles_sampled: bool
    minimum: float
    maximum: float
    mean: float
    median: float
    std: float = Field(ge=0)
    variance: float = Field(ge=0)
    dynamic_range: float = Field(ge=0)
    percentile_01: float
    percentile_05: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float
    percentile_99: float
    skewness: float
    excess_kurtosis: float


class HistogramData(BaseSchema):
    channel: str
    total_count: int = Field(ge=1)
    sample_count: int = Field(ge=1)
    sampled: bool
    bins: int = Field(ge=1)
    range_min: float
    range_max: float
    counts: list[int]
    probabilities: list[float]


class ImageHistograms(BaseSchema):
    gray: HistogramData | None = None
    rgb: dict[str, HistogramData] = Field(default_factory=dict)
    hsv: dict[str, HistogramData] = Field(default_factory=dict)


class ImageFeatures(BaseSchema):
    sampled: bool
    sample_width: int = Field(ge=1)
    sample_height: int = Field(ge=1)
    entropy_bits: float = Field(ge=0)
    rms_contrast: float = Field(ge=0)
    normalized_mean_intensity: float = Field(ge=0, le=1)
    normalized_std_intensity: float = Field(ge=0)
    dark_pixel_ratio: float = Field(ge=0, le=1)
    bright_pixel_ratio: float = Field(ge=0, le=1)
    nonzero_ratio: float = Field(ge=0, le=1)
    laplacian_variance: float = Field(ge=0)
    tenengrad: float = Field(ge=0)
    mean_gradient_magnitude: float = Field(ge=0)
    edge_density: float = Field(ge=0, le=1)
    center_of_mass_x: float | None = None
    center_of_mass_y: float | None = None
    mean_saturation: float | None = None
    mean_value: float | None = None
    colorfulness: float | None = Field(default=None, ge=0)


class ProjectionProfile(BaseSchema):
    axis: str
    original_length: int = Field(ge=1)
    sampled_length: int = Field(ge=1)
    downsampled: bool
    positions: list[float]
    sum_profile: list[float]
    mean_profile: list[float]
    derivative_profile: list[float] | None = None


class ImageProfiles(BaseSchema):
    x: ProjectionProfile | None = None
    y: ProjectionProfile | None = None


class ImageAnalysisResult(BaseSchema):
    metadata: AnalysisImageMetadata
    intensity_statistics: NumericStatistics
    channel_statistics: dict[str, NumericStatistics] = Field(default_factory=dict)
    histograms: ImageHistograms
    features: ImageFeatures | None = None
    profiles: ImageProfiles
