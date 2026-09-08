from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import Any

import cv2
import numpy as np
from scipy.signal import find_peaks

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
    ImageData,
    OperationCategory,
    OperationSpec,
)
from src.schemas.result import OperationOutput
from src.validators import ParameterValidator
from src.workflow.schemas import FeatureSpec, WorkflowDataKind, WorkflowPortSpec


FeatureHandler = Callable[[Mapping[str, Any], Mapping[str, Any]], OperationOutput]


@dataclass(frozen=True, slots=True)
class RegisteredFeature:
    spec: FeatureSpec
    handler: FeatureHandler


class FeatureRegistry:
    def __init__(self) -> None:
        self._items: dict[str, RegisteredFeature] = {}
        self._lock = RLock()

    def register(self, *, spec: FeatureSpec, handler: FeatureHandler) -> None:
        with self._lock:
            if spec.name in self._items:
                raise ValueError(f"feature already registered: {spec.name}")
            self._items[spec.name] = RegisteredFeature(
                spec=spec.model_copy(deep=True), handler=handler
            )

    def contains(self, name: str) -> bool:
        with self._lock:
            return name in self._items

    def get_spec(self, name: str) -> FeatureSpec:
        with self._lock:
            item = self._items.get(name)
        if item is None:
            raise KeyError(name)
        return item.spec.model_copy(deep=True)

    def list_specs(self) -> list[FeatureSpec]:
        with self._lock:
            return [
                self._items[name].spec.model_copy(deep=True)
                for name in sorted(self._items)
            ]

    def validate_params(self, name: str, params: Mapping[str, Any]) -> dict[str, Any]:
        spec = self.get_spec(name)
        pseudo = OperationSpec(
            name=spec.name,
            display_name=spec.display_name,
            category=OperationCategory.FEATURE,
            inputs=[],
            parameters=spec.parameters,
            outputs=[],
        )
        return ParameterValidator.validate_params(params=params, operation_spec=pseudo)

    def execute(
        self, *, name: str, inputs: Mapping[str, Any], params: Mapping[str, Any]
    ) -> OperationOutput:
        with self._lock:
            item = self._items.get(name)
        if item is None:
            raise KeyError(name)
        validated = self.validate_params(name, params)
        return item.handler(
            MappingProxyType(dict(inputs)), MappingProxyType(validated)
        )


def _gray_array(image: ImageData) -> np.ndarray:
    data = image.data
    if data.ndim == 2:
        return data
    if image.color_space.value in {"rgb", "rgba"}:
        code = cv2.COLOR_RGB2GRAY if data.shape[2] == 3 else cv2.COLOR_RGBA2GRAY
    else:
        code = cv2.COLOR_BGR2GRAY if data.shape[2] == 3 else cv2.COLOR_BGRA2GRAY
    return cv2.cvtColor(data, code)


def _pixel_stat_handler(inputs: Mapping[str, Any], params: Mapping[str, Any]) -> OperationOutput:
    image: ImageData = inputs["image"]
    array = image.data
    stat = params["statistic"]
    if stat == "sum":
        value = float(np.sum(array, dtype=np.float64))
    elif stat == "mean":
        value = float(np.mean(array, dtype=np.float64))
    elif stat == "min":
        value = float(np.min(array))
    elif stat == "max":
        value = float(np.max(array))
    elif stat == "median":
        value = float(np.median(array))
    elif stat == "std":
        value = float(np.std(array, dtype=np.float64))
    elif stat == "variance":
        value = float(np.var(array, dtype=np.float64))
    elif stat == "percentile":
        value = float(np.percentile(array, params["percentile"]))
    elif stat == "nonzero_count":
        value = float(np.count_nonzero(array))
    elif stat == "nonzero_ratio":
        value = float(np.count_nonzero(array) / array.size)
    else:
        raise ValueError(f"unsupported pixel statistic: {stat}")
    return OperationOutput(data={"value": value})


def _profile_handler(inputs: Mapping[str, Any], params: Mapping[str, Any]) -> OperationOutput:
    image: ImageData = inputs["image"]
    gray = _gray_array(image).astype(np.float64, copy=False)
    axis = params["axis"]
    reduce_axis = 0 if axis == "x" else 1
    if params["projection"] == "sum":
        profile = gray.sum(axis=reduce_axis, dtype=np.float64)
    else:
        profile = gray.mean(axis=reduce_axis, dtype=np.float64)

    window = params["smoothing_window"]
    if window > 1 and profile.size >= window:
        kernel = np.full(window, 1.0 / window, dtype=np.float64)
        profile = np.convolve(profile, kernel, mode="same")
    derivative = np.gradient(profile) if profile.size > 1 else np.zeros_like(profile)
    feature = params["feature"]
    if feature == "max":
        value = float(np.max(profile))
    elif feature == "min":
        value = float(np.min(profile))
    elif feature == "mean":
        value = float(np.mean(profile))
    elif feature == "std":
        value = float(np.std(profile))
    elif feature == "derivative_max_abs":
        value = float(np.max(np.abs(derivative)))
    elif feature == "derivative_max":
        value = float(np.max(derivative))
    elif feature == "derivative_min":
        value = float(np.min(derivative))
    else:
        peaks, properties = find_peaks(profile, prominence=params["peak_prominence"])
        if feature == "peak_count":
            value = float(len(peaks))
        elif feature == "peak_max":
            value = float(np.max(profile[peaks])) if len(peaks) else 0.0
        elif feature == "prominence_max":
            prominences = properties.get("prominences", np.array([], dtype=np.float64))
            value = float(np.max(prominences)) if prominences.size else 0.0
        else:
            raise ValueError(f"unsupported profile feature: {feature}")
    return OperationOutput(
        data={"value": value, "profile": profile, "derivative": derivative}
    )


def _contour_handler(inputs: Mapping[str, Any], params: Mapping[str, Any]) -> OperationOutput:
    image: ImageData = inputs["image"]
    gray = _gray_array(image)
    if gray.dtype != np.uint8:
        normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        gray = normalized.astype(np.uint8)
    mask = np.where(gray > 0, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = params["min_area"]
    contours = [c for c in contours if cv2.contourArea(c) >= min_area]
    areas = np.array([cv2.contourArea(c) for c in contours], dtype=np.float64)
    perimeters = np.array([cv2.arcLength(c, True) for c in contours], dtype=np.float64)
    image_area = float(mask.shape[0] * mask.shape[1])
    feature = params["feature"]
    if feature == "count":
        value = float(len(contours))
    elif feature == "largest_area":
        value = float(areas.max()) if areas.size else 0.0
    elif feature == "total_area":
        value = float(areas.sum())
    elif feature == "largest_area_ratio":
        value = float(areas.max() / image_area) if areas.size and image_area else 0.0
    elif feature == "largest_perimeter":
        value = float(perimeters.max()) if perimeters.size else 0.0
    elif feature in {"largest_circularity", "largest_solidity"}:
        if not contours:
            value = 0.0
        else:
            largest = max(contours, key=cv2.contourArea)
            area = float(cv2.contourArea(largest))
            perimeter = float(cv2.arcLength(largest, True))
            if feature == "largest_circularity":
                value = float(4.0 * np.pi * area / (perimeter * perimeter)) if perimeter else 0.0
            else:
                hull_area = float(cv2.contourArea(cv2.convexHull(largest)))
                value = float(area / hull_area) if hull_area else 0.0
    else:
        raise ValueError(f"unsupported contour feature: {feature}")
    return OperationOutput(
        data={
            "value": value,
            "features": {
                "count": len(contours),
                "areas": areas,
                "perimeters": perimeters,
            },
        }
    )


def _similarity_handler(inputs: Mapping[str, Any], params: Mapping[str, Any]) -> OperationOutput:
    a: ImageData = inputs["image"]
    b: ImageData = inputs["reference"]
    if a.data.shape != b.data.shape:
        raise ValueError("image and reference must have the same shape")
    x = a.data.astype(np.float64, copy=False)
    y = b.data.astype(np.float64, copy=False)
    metric = params["metric"]
    diff = x - y
    if metric == "mae":
        value = float(np.mean(np.abs(diff)))
    elif metric == "mse":
        value = float(np.mean(diff * diff))
    elif metric == "rmse":
        value = float(np.sqrt(np.mean(diff * diff)))
    elif metric == "ncc":
        xc = x - x.mean()
        yc = y - y.mean()
        denom = float(np.sqrt(np.sum(xc * xc) * np.sum(yc * yc)))
        value = float(np.sum(xc * yc) / denom) if denom else 1.0 if np.array_equal(x, y) else 0.0
    elif metric == "global_ssim":
        dynamic_range = float(max(np.max(x), np.max(y)) - min(np.min(x), np.min(y))) or 1.0
        c1 = (0.01 * dynamic_range) ** 2
        c2 = (0.03 * dynamic_range) ** 2
        ux, uy = float(x.mean()), float(y.mean())
        vx, vy = float(x.var()), float(y.var())
        covariance = float(np.mean((x - ux) * (y - uy)))
        value = float(((2 * ux * uy + c1) * (2 * covariance + c2)) / ((ux * ux + uy * uy + c1) * (vx + vy + c2)))
    else:
        raise ValueError(f"unsupported similarity metric: {metric}")
    return OperationOutput(data={"value": value})


def _mask_similarity_handler(inputs: Mapping[str, Any], params: Mapping[str, Any]) -> OperationOutput:
    a: ImageData = inputs["image"]
    b: ImageData = inputs["reference"]
    if a.data.shape[:2] != b.data.shape[:2]:
        raise ValueError("mask and reference must have the same width/height")
    ma = _gray_array(a) > 0
    mb = _gray_array(b) > 0
    intersection = int(np.count_nonzero(ma & mb))
    union = int(np.count_nonzero(ma | mb))
    count_a = int(np.count_nonzero(ma))
    count_b = int(np.count_nonzero(mb))
    metric = params["metric"]
    if metric == "iou":
        value = float(intersection / union) if union else 1.0
    elif metric == "dice":
        denom = count_a + count_b
        value = float(2 * intersection / denom) if denom else 1.0
    elif metric == "mismatch_ratio":
        value = float(np.count_nonzero(ma != mb) / ma.size)
    else:
        raise ValueError(f"unsupported mask similarity metric: {metric}")
    return OperationOutput(data={"value": value})


def create_default_feature_registry() -> FeatureRegistry:
    registry = FeatureRegistry()
    registry.register(
        spec=FeatureSpec(
            name="pixel_statistic",
            display_name="Pixel Statistic",
            category="pixel",
            description="이미지 픽셀을 하나의 통계값으로 축약합니다.",
            inputs=[WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE)],
            parameters={
                "statistic": CategoryParameterSpec(
                    title="Statistic",
                    choices=[CategoryChoice(value=v, label=v.replace("_", " ").title()) for v in [
                        "sum", "mean", "min", "max", "median", "std", "variance",
                        "percentile", "nonzero_count", "nonzero_ratio",
                    ]],
                    default="mean",
                ),
                "percentile": ContinuousParameterSpec(
                    title="Percentile", min_value=0.0, max_value=100.0, default=50.0
                ),
            },
            outputs=[WorkflowPortSpec(name="value", kind=WorkflowDataKind.SCALAR)],
        ),
        handler=_pixel_stat_handler,
    )
    registry.register(
        spec=FeatureSpec(
            name="profile_feature",
            display_name="Projection Profile Feature",
            category="profile",
            description="X/Y projection과 미분/peak 특징을 추출합니다.",
            inputs=[WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE)],
            parameters={
                "axis": CategoryParameterSpec(
                    title="Axis",
                    choices=[CategoryChoice(value="x", label="X"), CategoryChoice(value="y", label="Y")],
                    default="x",
                ),
                "projection": CategoryParameterSpec(
                    title="Projection",
                    choices=[CategoryChoice(value="sum", label="Sum"), CategoryChoice(value="mean", label="Mean")],
                    default="sum",
                ),
                "feature": CategoryParameterSpec(
                    title="Feature",
                    choices=[CategoryChoice(value=v, label=v.replace("_", " ").title()) for v in [
                        "max", "min", "mean", "std", "derivative_max_abs",
                        "derivative_max", "derivative_min", "peak_count", "peak_max", "prominence_max",
                    ]],
                    default="derivative_max_abs",
                ),
                "smoothing_window": DiscreteParameterSpec(
                    title="Smoothing Window", min_value=1, max_value=99, step=2, default=3
                ),
                "peak_prominence": ContinuousParameterSpec(
                    title="Peak Prominence", min_value=0.0, max_value=1_000_000_000.0, default=0.0
                ),
            },
            outputs=[
                WorkflowPortSpec(name="value", kind=WorkflowDataKind.SCALAR),
                WorkflowPortSpec(name="profile", kind=WorkflowDataKind.PROFILE),
                WorkflowPortSpec(name="derivative", kind=WorkflowDataKind.PROFILE),
            ],
        ),
        handler=_profile_handler,
    )
    registry.register(
        spec=FeatureSpec(
            name="contour_feature",
            display_name="Contour Feature",
            category="shape",
            description="Binary-like 이미지의 contour 형상 특징을 하나의 값으로 축약합니다.",
            inputs=[WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE)],
            parameters={
                "feature": CategoryParameterSpec(
                    title="Feature",
                    choices=[CategoryChoice(value=v, label=v.replace("_", " ").title()) for v in [
                        "count", "largest_area", "total_area", "largest_area_ratio",
                        "largest_perimeter", "largest_circularity", "largest_solidity",
                    ]],
                    default="largest_area_ratio",
                ),
                "min_area": ContinuousParameterSpec(
                    title="Minimum Area", min_value=0.0, max_value=1_000_000_000.0, default=0.0
                ),
            },
            outputs=[
                WorkflowPortSpec(name="value", kind=WorkflowDataKind.SCALAR),
                WorkflowPortSpec(name="features", kind=WorkflowDataKind.METRICS),
            ],
        ),
        handler=_contour_handler,
    )
    registry.register(
        spec=FeatureSpec(
            name="image_similarity",
            display_name="Image Similarity",
            category="similarity",
            description="동일 크기 이미지 사이의 오차/상관/전역 SSIM 값을 계산합니다.",
            inputs=[
                WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE),
                WorkflowPortSpec(name="reference", kind=WorkflowDataKind.IMAGE),
            ],
            parameters={
                "metric": CategoryParameterSpec(
                    title="Metric",
                    choices=[CategoryChoice(value=v, label=v.upper()) for v in ["mae", "mse", "rmse", "ncc", "global_ssim"]],
                    default="mae",
                )
            },
            outputs=[WorkflowPortSpec(name="value", kind=WorkflowDataKind.SCALAR)],
        ),
        handler=_similarity_handler,
    )
    registry.register(
        spec=FeatureSpec(
            name="mask_similarity",
            display_name="Mask Similarity",
            category="similarity",
            description="두 binary-like mask의 IoU/Dice/mismatch ratio를 계산합니다.",
            inputs=[
                WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE),
                WorkflowPortSpec(name="reference", kind=WorkflowDataKind.IMAGE),
            ],
            parameters={
                "metric": CategoryParameterSpec(
                    title="Metric",
                    choices=[CategoryChoice(value=v, label=v.upper()) for v in ["iou", "dice", "mismatch_ratio"]],
                    default="iou",
                )
            },
            outputs=[WorkflowPortSpec(name="value", kind=WorkflowDataKind.SCALAR)],
        ),
        handler=_mask_similarity_handler,
    )
    return registry
