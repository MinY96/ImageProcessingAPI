from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
    ImageData,
    InputKind,
    InputSlotSpec,
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)

from ..common import as_image, ensure_pixel_budget
from ..feature.common import to_gray_u8
from ..matching.feature import extract_and_match


ESTIMATE_HOMOGRAPHY_SPEC = OperationSpec(
    name="estimate_homography",
    display_name="Estimate Homography",
    category=OperationCategory.REGISTRATION,
    inputs=[
        InputSlotSpec(name="source_points", kind=InputKind.POINTS),
        InputSlotSpec(name="destination_points", kind=InputKind.POINTS),
    ],
    parameters={
        "method": CategoryParameterSpec(
            title="Method",
            choices=[
                CategoryChoice(value="ransac", label="RANSAC"),
                CategoryChoice(value="lmeds", label="Least Median"),
                CategoryChoice(value="direct", label="Direct"),
            ],
            default="ransac",
        ),
        "reprojection_threshold": ContinuousParameterSpec(
            title="Reprojection Threshold",
            min_value=0.1,
            max_value=100.0,
            default=5.0,
        ),
    },
    outputs=[
        OutputSlotSpec(name="homography", kind=OutputKind.ARRAY),
        OutputSlotSpec(name="inlier_mask", kind=OutputKind.ARRAY),
    ],
)


LOCALIZE_PLANAR_OBJECT_SPEC = OperationSpec(
    name="localize_planar_object",
    display_name="Localize Planar Object",
    category=OperationCategory.REGISTRATION,
    inputs=[
        InputSlotSpec(name="query_image", kind=InputKind.TEMPLATE),
        InputSlotSpec(name="scene_image", kind=InputKind.IMAGE),
    ],
    parameters={
        "algorithm": CategoryParameterSpec(
            title="Feature Algorithm",
            choices=[
                CategoryChoice(value="sift", label="SIFT"),
                CategoryChoice(value="orb", label="ORB"),
            ],
            default="sift",
        ),
        "matcher": CategoryParameterSpec(
            title="Matcher",
            choices=[
                CategoryChoice(value="flann", label="FLANN"),
                CategoryChoice(value="bf", label="Brute Force"),
            ],
            default="flann",
        ),
        "max_features": DiscreteParameterSpec(
            title="Maximum Features", min_value=10, max_value=20000, default=3000
        ),
        "ratio_threshold": ContinuousParameterSpec(
            title="Lowe Ratio Threshold", min_value=0.1, max_value=0.99, default=0.7
        ),
        "min_matches": DiscreteParameterSpec(
            title="Minimum Matches", min_value=4, max_value=1000, default=10
        ),
        "max_matches": DiscreteParameterSpec(
            title="Maximum Matches", min_value=4, max_value=10000, default=500
        ),
        "reprojection_threshold": ContinuousParameterSpec(
            title="RANSAC Reprojection Threshold",
            min_value=0.1,
            max_value=100.0,
            default=5.0,
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="homography", kind=OutputKind.ARRAY),
        OutputSlotSpec(name="polygon", kind=OutputKind.ARRAY),
        OutputSlotSpec(name="metrics", kind=OutputKind.METRICS),
    ],
)


def _points(value: Any, name: str) -> np.ndarray:
    try:
        points = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise OperationExecutionError(
            code="invalid_points", message=f"{name} must contain numeric points"
        ) from exc
    if points.ndim == 3 and points.shape[1:] == (1, 2):
        points = points.reshape(-1, 2)
    if points.ndim != 2 or points.shape[0] < 4 or points.shape[1] != 2:
        raise OperationExecutionError(
            code="invalid_points",
            message=f"{name} must have shape (N, 2), N >= 4",
            details={"shape": list(points.shape)},
        )
    if not np.isfinite(points).all():
        raise OperationExecutionError(
            code="invalid_points", message=f"{name} must contain finite coordinates"
        )
    return np.ascontiguousarray(points)


def _homography(source: np.ndarray, destination: np.ndarray, method: str, threshold: float):
    import cv2

    if source.shape != destination.shape:
        raise OperationExecutionError(
            code="incompatible_points",
            message="source_points and destination_points must have the same shape",
        )
    methods = {"ransac": cv2.RANSAC, "lmeds": cv2.LMEDS, "direct": 0}
    matrix, mask = cv2.findHomography(
        source.reshape(-1, 1, 2),
        destination.reshape(-1, 1, 2),
        methods[method],
        threshold,
    )
    if matrix is None:
        raise OperationExecutionError(
            code="homography_estimation_failed",
            message="OpenCV could not estimate a homography from the points",
        )
    if mask is None:
        mask = np.ones((source.shape[0], 1), dtype=np.uint8)
    return matrix.astype(np.float64), mask.reshape(-1).astype(np.uint8)


def estimate_homography_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    source = _points(inputs["source_points"], "source_points")
    destination = _points(inputs["destination_points"], "destination_points")
    matrix, mask = _homography(
        source, destination, params["method"], params["reprojection_threshold"]
    )
    return OperationOutput(data={"homography": matrix, "inlier_mask": mask})


def localize_planar_object_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    query: ImageData = inputs["query_image"]
    scene: ImageData = inputs["scene_image"]
    ensure_pixel_budget(
        pixels=query.width * query.height + scene.width * scene.height,
        operation="localize_planar_object",
        max_pixels=24_000_000,
    )
    result = extract_and_match(
        query,
        scene,
        algorithm=params["algorithm"],
        matcher_name=params["matcher"],
        max_features=params["max_features"],
        ratio_threshold=params["ratio_threshold"],
        max_matches=params["max_matches"],
    )
    if len(result.matches) < params["min_matches"]:
        raise OperationExecutionError(
            code="insufficient_matches",
            message="not enough good matches to estimate homography",
            details={"matches": len(result.matches), "required": params["min_matches"]},
        )
    source = np.float32(
        [result.keypoints1[item.queryIdx].pt for item in result.matches]
    )
    destination = np.float32(
        [result.keypoints2[item.trainIdx].pt for item in result.matches]
    )
    matrix, mask = _homography(
        source, destination, "ransac", params["reprojection_threshold"]
    )
    corners = np.float32(
        [[0, 0], [query.width - 1, 0], [query.width - 1, query.height - 1], [0, query.height - 1]]
    ).reshape(-1, 1, 2)
    polygon = cv2.perspectiveTransform(corners, matrix).reshape(-1, 2)
    scene_rendered = cv2.cvtColor(to_gray_u8(scene), cv2.COLOR_GRAY2BGR)
    cv2.polylines(
        scene_rendered,
        [np.int32(np.round(polygon)).reshape(-1, 1, 2)],
        True,
        (0, 0, 255),
        3,
        cv2.LINE_AA,
    )
    inliers = int(mask.sum())
    return OperationOutput(
        images={
            "image": as_image(
                scene_rendered,
                source=scene,
                color_space=ColorSpace.BGR,
                name="localized_object",
            )
        },
        data={
            "homography": matrix,
            "polygon": polygon.astype(np.float32),
            "metrics": {
                "good_matches": len(result.matches),
                "inliers": inliers,
                "inlier_ratio": inliers / max(1, len(result.matches)),
                "algorithm": params["algorithm"],
                "matcher": params["matcher"],
            },
        },
    )
