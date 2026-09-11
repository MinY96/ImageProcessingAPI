from __future__ import annotations

import math

import cv2
import numpy as np

from src.schemas import ColorSpace, ImageData

from .schemas import (
    AnalysisImageMetadata,
    AnalysisOptions,
    HistogramData,
    ImageAnalysisResult,
    ImageFeatures,
    ImageHistograms,
    ImageProfiles,
    NumericStatistics,
    ProjectionProfile,
)


class ImageAnalyzer:
    """Stateless numerical analysis for original and processed ImageData."""

    def analyze(
        self,
        image: ImageData,
        *,
        options: AnalysisOptions | None = None,
        source_size_bytes: int | None = None,
    ) -> ImageAnalysisResult:
        resolved = options or AnalysisOptions()
        gray = _to_gray(image)
        gray_values = _finite_values(gray)
        gray_statistics = _statistics(
            gray_values,
            sample_max=resolved.statistics_sample_max_pixels,
        )

        histograms = ImageHistograms()
        if resolved.include_gray_histogram:
            histograms.gray = _histogram(
                gray_values,
                channel="gray",
                bins=resolved.histogram_bins,
                dtype=gray.dtype,
            )

        rgb_channels = _rgb_channels(image)
        channel_statistics: dict[str, NumericStatistics] = {}
        if rgb_channels:
            if resolved.include_rgb_histogram:
                histograms.rgb = {
                    name: _histogram(
                        _finite_values(channel),
                        channel=name,
                        bins=resolved.histogram_bins,
                        dtype=channel.dtype,
                    )
                    for name, channel in rgb_channels.items()
                }
            if resolved.include_channel_statistics:
                channel_statistics = {
                    name: _statistics(
                        _finite_values(channel),
                        sample_max=resolved.statistics_sample_max_pixels,
                    )
                    for name, channel in rgb_channels.items()
                }

        hsv_channels, hsv_sampled, hsv_total_count = _hsv_channels(
            image,
            max_pixels=resolved.derived_color_max_pixels,
        )
        if hsv_channels and resolved.include_hsv_histogram:
            histograms.hsv = {
                name: _histogram_with_range(
                    _finite_values(channel),
                    channel=name,
                    bins=(
                        180
                        if name == "h" and resolved.histogram_bins >= 180
                        else resolved.histogram_bins
                    ),
                    range_min=0.0,
                    range_max=(180.0 if name == "h" else 256.0),
                    total_count=hsv_total_count,
                    sampled=hsv_sampled,
                )
                for name, channel in hsv_channels.items()
            }

        features = None
        if resolved.include_features:
            features = _features(
                gray=gray,
                gray_values=gray_values,
                statistics=gray_statistics,
                image=image,
                max_pixels=resolved.feature_max_pixels,
            )

        profiles = ImageProfiles()
        if resolved.include_profiles:
            profiles = _profiles(
                gray,
                max_points=resolved.profile_max_points,
                smoothing_window=resolved.profile_smoothing_window,
                include_derivative=resolved.include_profile_derivative,
            )

        return ImageAnalysisResult(
            metadata=AnalysisImageMetadata(
                name=image.name,
                width=image.width,
                height=image.height,
                channels=image.channels,
                pixel_count=image.width * image.height,
                dtype=image.dtype,
                bit_depth_per_channel=int(image.data.dtype.itemsize * 8),
                bits_per_pixel=int(image.data.dtype.itemsize * 8 * image.channels),
                color_space=image.color_space,
                shape=list(image.shape),
                aspect_ratio=float(image.width / image.height),
                decoded_size_bytes=int(image.data.nbytes),
                source_size_bytes=source_size_bytes,
            ),
            intensity_statistics=gray_statistics,
            channel_statistics=channel_statistics,
            histograms=histograms,
            features=features,
            profiles=profiles,
        )


def _finite_values(array: np.ndarray) -> np.ndarray:
    values = np.asarray(array).reshape(-1)
    if np.issubdtype(values.dtype, np.floating):
        finite_mask = np.isfinite(values)
        if not bool(np.all(finite_mask)):
            values = values[finite_mask]
    if values.size == 0:
        return np.array([0.0], dtype=np.float32)
    return values


def _sample_1d(values: np.ndarray, max_items: int) -> tuple[np.ndarray, bool]:
    if values.size <= max_items:
        return values, False
    step = int(math.ceil(values.size / max_items))
    return values[::step], True


def _statistics(values: np.ndarray, *, sample_max: int) -> NumericStatistics:
    total_count = int(values.size)
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    mean = float(np.mean(values, dtype=np.float64))
    variance = float(np.var(values, dtype=np.float64))
    std = math.sqrt(max(0.0, variance))

    sample, sampled = _sample_1d(values, sample_max)
    sample64 = sample.astype(np.float64, copy=False)
    percentiles = np.percentile(sample64, [1, 5, 25, 50, 75, 95, 99])

    if std > 0.0:
        centered = (sample64 - mean) / std
        skewness = float(np.mean(centered * centered * centered))
        squared = centered * centered
        excess_kurtosis = float(np.mean(squared * squared) - 3.0)
    else:
        skewness = 0.0
        excess_kurtosis = 0.0

    return NumericStatistics(
        total_count=total_count,
        sample_count=int(sample.size),
        quantiles_sampled=sampled,
        minimum=minimum,
        maximum=maximum,
        mean=mean,
        median=float(percentiles[3]),
        std=std,
        variance=variance,
        dynamic_range=float(maximum - minimum),
        percentile_01=float(percentiles[0]),
        percentile_05=float(percentiles[1]),
        percentile_25=float(percentiles[2]),
        percentile_50=float(percentiles[3]),
        percentile_75=float(percentiles[4]),
        percentile_95=float(percentiles[5]),
        percentile_99=float(percentiles[6]),
        skewness=skewness,
        excess_kurtosis=excess_kurtosis,
    )


def _histogram(
    values: np.ndarray,
    *,
    channel: str,
    bins: int,
    dtype: np.dtype,
) -> HistogramData:
    range_min, range_max = _histogram_range(values, dtype)
    return _histogram_with_range(
        values,
        channel=channel,
        bins=bins,
        range_min=range_min,
        range_max=range_max,
        total_count=int(values.size),
        sampled=False,
    )


def _histogram_range(values: np.ndarray, dtype: np.dtype) -> tuple[float, float]:
    dtype = np.dtype(dtype)
    if dtype == np.dtype(np.uint8):
        return 0.0, 256.0
    if dtype == np.dtype(np.uint16):
        return 0.0, 65536.0
    if dtype == np.dtype(np.int16):
        return -32768.0, 32768.0

    minimum = float(np.min(values))
    maximum = float(np.max(values))
    if not math.isfinite(minimum) or not math.isfinite(maximum):
        return 0.0, 1.0
    if minimum == maximum:
        return minimum - 0.5, maximum + 0.5
    return minimum, maximum


def _histogram_with_range(
    values: np.ndarray,
    *,
    channel: str,
    bins: int,
    range_min: float,
    range_max: float,
    total_count: int,
    sampled: bool,
) -> HistogramData:
    counts, _ = np.histogram(
        values,
        bins=bins,
        range=(range_min, range_max),
    )
    sample_count = int(counts.sum())
    probabilities = (
        counts.astype(np.float64) / sample_count
        if sample_count > 0
        else np.zeros_like(counts, dtype=np.float64)
    )
    return HistogramData(
        channel=channel,
        total_count=max(1, total_count),
        sample_count=max(1, sample_count),
        sampled=sampled,
        bins=bins,
        range_min=range_min,
        range_max=range_max,
        counts=[int(value) for value in counts],
        probabilities=[float(value) for value in probabilities],
    )


def _to_gray(image: ImageData) -> np.ndarray:
    array = image.data
    space = image.color_space
    if array.ndim == 2 or space in {ColorSpace.GRAY, ColorSpace.BINARY}:
        return array

    conversions = {
        ColorSpace.BGR: cv2.COLOR_BGR2GRAY,
        ColorSpace.RGB: cv2.COLOR_RGB2GRAY,
        ColorSpace.BGRA: cv2.COLOR_BGRA2GRAY,
        ColorSpace.RGBA: cv2.COLOR_RGBA2GRAY,
    }
    conversion = conversions.get(space)
    if conversion is not None:
        try:
            return cv2.cvtColor(array, conversion)
        except cv2.error:
            pass

    return cv2.cvtColor(_to_bgr8(image), cv2.COLOR_BGR2GRAY)


def _rgb_channels(image: ImageData) -> dict[str, np.ndarray]:
    array = image.data
    space = image.color_space
    if image.channels < 3:
        return {}

    if space in {ColorSpace.BGR, ColorSpace.BGRA}:
        return {"r": array[..., 2], "g": array[..., 1], "b": array[..., 0]}
    if space in {ColorSpace.RGB, ColorSpace.RGBA}:
        return {"r": array[..., 0], "g": array[..., 1], "b": array[..., 2]}

    rgb8 = cv2.cvtColor(_to_bgr8(image), cv2.COLOR_BGR2RGB)
    return {"r": rgb8[..., 0], "g": rgb8[..., 1], "b": rgb8[..., 2]}


def _hsv_channels(
    image: ImageData,
    *,
    max_pixels: int,
) -> tuple[dict[str, np.ndarray], bool, int]:
    if image.channels < 3:
        return {}, False, image.width * image.height

    source = image.data
    total_count = image.width * image.height
    sampled = total_count > max_pixels

    if sampled:
        source = _resize_to_max_pixels(source, max_pixels)
        sampled_image = ImageData(
            data=source,
            color_space=image.color_space,
            name=image.name,
        )
    else:
        sampled_image = image

    if sampled_image.color_space == ColorSpace.HSV and source.dtype == np.uint8:
        hsv = source[..., :3]
    else:
        hsv = cv2.cvtColor(_to_bgr8(sampled_image), cv2.COLOR_BGR2HSV)

    return (
        {"h": hsv[..., 0], "s": hsv[..., 1], "v": hsv[..., 2]},
        sampled,
        total_count,
    )


def _to_bgr8(image: ImageData) -> np.ndarray:
    array = image.data
    space = image.color_space

    if space == ColorSpace.BGR and array.dtype == np.uint8:
        return array
    if space == ColorSpace.BGRA and array.dtype == np.uint8:
        return cv2.cvtColor(array, cv2.COLOR_BGRA2BGR)
    if space == ColorSpace.RGB and array.dtype == np.uint8:
        return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    if space == ColorSpace.RGBA and array.dtype == np.uint8:
        return cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)
    if space == ColorSpace.HSV and array.dtype == np.uint8:
        return cv2.cvtColor(array[..., :3], cv2.COLOR_HSV2BGR)
    if space == ColorSpace.LAB and array.dtype == np.uint8:
        return cv2.cvtColor(array[..., :3], cv2.COLOR_LAB2BGR)

    if array.ndim == 2:
        normalized = _normalize_uint8(array)
        return cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)

    normalized = _normalize_uint8(array[..., :3])
    if space in {ColorSpace.RGB, ColorSpace.RGBA}:
        return cv2.cvtColor(normalized, cv2.COLOR_RGB2BGR)
    if space == ColorSpace.HSV:
        return cv2.cvtColor(normalized, cv2.COLOR_HSV2BGR)
    if space == ColorSpace.LAB:
        return cv2.cvtColor(normalized, cv2.COLOR_LAB2BGR)
    return normalized


def _normalize_uint8(array: np.ndarray) -> np.ndarray:
    if array.dtype == np.uint8:
        return array
    if array.dtype == np.uint16:
        return np.right_shift(array, 8).astype(np.uint8)

    values = array.astype(np.float32, copy=False)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.zeros(array.shape, dtype=np.uint8)
    minimum = float(np.min(finite))
    maximum = float(np.max(finite))
    if maximum <= minimum:
        return np.zeros(array.shape, dtype=np.uint8)
    scaled = (values - minimum) * (255.0 / (maximum - minimum))
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=255.0, neginf=0.0)
    return np.clip(scaled, 0, 255).astype(np.uint8)


def _resize_to_max_pixels(array: np.ndarray, max_pixels: int) -> np.ndarray:
    height, width = array.shape[:2]
    pixels = height * width
    if pixels <= max_pixels:
        return array
    scale = math.sqrt(max_pixels / pixels)
    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))
    return cv2.resize(array, (new_width, new_height), interpolation=cv2.INTER_AREA)


def _features(
    *,
    gray: np.ndarray,
    gray_values: np.ndarray,
    statistics: NumericStatistics,
    image: ImageData,
    max_pixels: int,
) -> ImageFeatures:
    gray_sample = _resize_to_max_pixels(gray, max_pixels)
    sampled = gray_sample.shape[:2] != gray.shape[:2]
    gray8 = _normalize_uint8(gray_sample)

    total_range = _dtype_total_range(gray.dtype, gray_values)
    normalized_mean = _normalized_intensity(statistics.mean, gray.dtype, gray_values)
    normalized_std = statistics.std / total_range if total_range > 0 else 0.0

    low, high = _clipping_thresholds(gray.dtype, gray_values)
    dark_ratio = float(np.mean(gray_values <= low))
    bright_ratio = float(np.mean(gray_values >= high))
    nonzero_ratio = float(np.mean(gray_values != 0))

    hist_counts = np.bincount(gray8.reshape(-1), minlength=256).astype(np.float64)
    probabilities = hist_counts / max(1.0, hist_counts.sum())
    positive = probabilities[probabilities > 0]
    entropy = float(-np.sum(positive * np.log2(positive)))

    laplacian = cv2.Laplacian(gray8, cv2.CV_32F)
    laplacian_variance = float(np.var(laplacian, dtype=np.float64))
    gx = cv2.Sobel(gray8, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray8, cv2.CV_32F, 0, 1, ksize=3)
    magnitude_sq = gx * gx + gy * gy
    tenengrad = float(np.mean(magnitude_sq, dtype=np.float64))
    mean_gradient = float(np.mean(np.sqrt(magnitude_sq), dtype=np.float64))

    median = float(np.median(gray8))
    lower = int(max(0.0, 0.66 * median))
    upper = int(min(255.0, 1.33 * median))
    if upper <= lower:
        lower, upper = 50, 150
    edges = cv2.Canny(gray8, lower, upper)
    edge_density = float(np.count_nonzero(edges) / edges.size)

    weights = gray8.astype(np.float32)
    mass = float(np.sum(weights, dtype=np.float64))
    center_x = None
    center_y = None
    if mass > 0:
        x_weights = np.sum(weights, axis=0, dtype=np.float64)
        y_weights = np.sum(weights, axis=1, dtype=np.float64)
        sample_center_x = float(np.dot(np.arange(gray8.shape[1]), x_weights) / mass)
        sample_center_y = float(np.dot(np.arange(gray8.shape[0]), y_weights) / mass)
        center_x = sample_center_x * (image.width / gray8.shape[1])
        center_y = sample_center_y * (image.height / gray8.shape[0])

    mean_saturation = None
    mean_value = None
    colorfulness = None
    if image.channels >= 3:
        color_source = _resize_to_max_pixels(image.data, max_pixels)
        sampled_color = ImageData(
            data=color_source,
            color_space=image.color_space,
            name=image.name,
        )
        bgr8 = _to_bgr8(sampled_color)
        hsv = cv2.cvtColor(bgr8, cv2.COLOR_BGR2HSV)
        mean_saturation = float(np.mean(hsv[..., 1], dtype=np.float64) / 255.0)
        mean_value = float(np.mean(hsv[..., 2], dtype=np.float64) / 255.0)

        b, g, r = cv2.split(bgr8.astype(np.float32))
        rg = r - g
        yb = 0.5 * (r + g) - b
        std_root = math.sqrt(float(np.var(rg, dtype=np.float64) + np.var(yb, dtype=np.float64)))
        mean_root = math.sqrt(float(np.mean(rg, dtype=np.float64) ** 2 + np.mean(yb, dtype=np.float64) ** 2))
        colorfulness = float(std_root + 0.3 * mean_root)

    return ImageFeatures(
        sampled=sampled,
        sample_width=int(gray8.shape[1]),
        sample_height=int(gray8.shape[0]),
        entropy_bits=entropy,
        rms_contrast=statistics.std,
        normalized_mean_intensity=float(np.clip(normalized_mean, 0.0, 1.0)),
        normalized_std_intensity=max(0.0, normalized_std),
        dark_pixel_ratio=dark_ratio,
        bright_pixel_ratio=bright_ratio,
        nonzero_ratio=nonzero_ratio,
        laplacian_variance=max(0.0, laplacian_variance),
        tenengrad=max(0.0, tenengrad),
        mean_gradient_magnitude=max(0.0, mean_gradient),
        edge_density=float(np.clip(edge_density, 0.0, 1.0)),
        center_of_mass_x=center_x,
        center_of_mass_y=center_y,
        mean_saturation=mean_saturation,
        mean_value=mean_value,
        colorfulness=colorfulness,
    )


def _dtype_total_range(dtype: np.dtype, values: np.ndarray) -> float:
    dtype = np.dtype(dtype)
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        return float(info.max - info.min)
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    return max(0.0, maximum - minimum)


def _normalized_intensity(mean: float, dtype: np.dtype, values: np.ndarray) -> float:
    dtype = np.dtype(dtype)
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        denominator = float(info.max - info.min)
        return (mean - float(info.min)) / denominator if denominator > 0 else 0.0
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    return (mean - minimum) / (maximum - minimum) if maximum > minimum else 0.0


def _clipping_thresholds(dtype: np.dtype, values: np.ndarray) -> tuple[float, float]:
    dtype = np.dtype(dtype)
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        span = float(info.max - info.min)
        return float(info.min) + 0.01 * span, float(info.max) - 0.01 * span
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    span = maximum - minimum
    return minimum + 0.01 * span, maximum - 0.01 * span


def _profiles(
    gray: np.ndarray,
    *,
    max_points: int,
    smoothing_window: int,
    include_derivative: bool,
) -> ImageProfiles:
    x_sum = np.sum(gray, axis=0, dtype=np.float64)
    y_sum = np.sum(gray, axis=1, dtype=np.float64)
    x_mean = x_sum / max(1, gray.shape[0])
    y_mean = y_sum / max(1, gray.shape[1])

    return ImageProfiles(
        x=_projection_profile(
            "x",
            x_sum,
            x_mean,
            max_points=max_points,
            smoothing_window=smoothing_window,
            include_derivative=include_derivative,
        ),
        y=_projection_profile(
            "y",
            y_sum,
            y_mean,
            max_points=max_points,
            smoothing_window=smoothing_window,
            include_derivative=include_derivative,
        ),
    )


def _projection_profile(
    axis: str,
    sum_values: np.ndarray,
    mean_values: np.ndarray,
    *,
    max_points: int,
    smoothing_window: int,
    include_derivative: bool,
) -> ProjectionProfile:
    original_length = int(sum_values.size)
    positions = np.arange(original_length, dtype=np.float64)
    downsampled = original_length > max_points

    if downsampled:
        edges = np.linspace(0, original_length, max_points + 1, dtype=np.int64)
        sampled_positions = np.empty(max_points, dtype=np.float64)
        sampled_sum = np.empty(max_points, dtype=np.float64)
        sampled_mean = np.empty(max_points, dtype=np.float64)
        for index in range(max_points):
            start = int(edges[index])
            end = int(edges[index + 1])
            if end <= start:
                end = min(original_length, start + 1)
            sampled_positions[index] = float((start + end - 1) / 2.0)
            sampled_sum[index] = float(np.mean(sum_values[start:end]))
            sampled_mean[index] = float(np.mean(mean_values[start:end]))
        positions, sum_values, mean_values = sampled_positions, sampled_sum, sampled_mean

    smoothed_mean = _moving_average(mean_values, smoothing_window)
    smoothed_sum = _moving_average(sum_values, smoothing_window)
    derivative = None
    if include_derivative:
        if smoothed_sum.size <= 1:
            derivative = np.zeros_like(smoothed_sum)
        else:
            derivative = np.gradient(smoothed_sum, positions)

    return ProjectionProfile(
        axis=axis,
        original_length=original_length,
        sampled_length=int(positions.size),
        downsampled=downsampled,
        positions=[float(value) for value in positions],
        sum_profile=[float(value) for value in sum_values],
        mean_profile=[float(value) for value in smoothed_mean],
        derivative_profile=(
            [float(value) for value in derivative]
            if derivative is not None
            else None
        ),
    )


def _moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or values.size < window:
        return values.astype(np.float64, copy=False)
    kernel = np.ones(window, dtype=np.float64) / window
    padded = np.pad(values, (window // 2, window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")
