from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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


@dataclass(slots=True)
class FeatureMatches:
    keypoints1: list[Any]
    keypoints2: list[Any]
    descriptors1: np.ndarray
    descriptors2: np.ndarray
    matches: list[Any]


def extract_and_match(
    image1: ImageData,
    image2: ImageData,
    *,
    algorithm: str,
    matcher_name: str,
    max_features: int,
    ratio_threshold: float,
    max_matches: int,
) -> FeatureMatches:
    import cv2

    gray1, gray2 = to_gray_u8(image1), to_gray_u8(image2)
    if algorithm == "sift":
        detector = cv2.SIFT_create(nfeatures=max_features)
        norm = cv2.NORM_L2
        descriptor_kind = "float"
    elif algorithm == "orb":
        detector = cv2.ORB_create(nfeatures=max_features)
        norm = cv2.NORM_HAMMING
        descriptor_kind = "binary"
    else:
        raise OperationExecutionError(
            code="unsupported_feature_algorithm",
            message=f"unsupported feature algorithm: {algorithm}",
        )

    keypoints1, descriptors1 = detector.detectAndCompute(gray1, None)
    keypoints2, descriptors2 = detector.detectAndCompute(gray2, None)
    if descriptors1 is None or descriptors2 is None:
        raise OperationExecutionError(
            code="insufficient_features",
            message="features could not be extracted from both images",
            details={
                "image1_keypoints": len(keypoints1),
                "image2_keypoints": len(keypoints2),
            },
        )

    if matcher_name == "bf":
        matcher = cv2.BFMatcher(normType=norm, crossCheck=False)
    elif matcher_name == "flann" and descriptor_kind == "float":
        matcher = cv2.FlannBasedMatcher(
            {"algorithm": 1, "trees": 5}, {"checks": 50}
        )
    elif matcher_name == "flann":
        matcher = cv2.FlannBasedMatcher(
            {
                "algorithm": 6,
                "table_number": 6,
                "key_size": 12,
                "multi_probe_level": 1,
            },
            {"checks": 50},
        )
    else:
        raise OperationExecutionError(
            code="unsupported_matcher", message=f"unsupported matcher: {matcher_name}"
        )

    try:
        pairs = matcher.knnMatch(descriptors1, descriptors2, k=2)
    except cv2.error as exc:
        raise OperationExecutionError(
            code="feature_matching_failed",
            message="OpenCV failed while matching descriptors",
            details={"algorithm": algorithm, "matcher": matcher_name},
        ) from exc

    good = [
        first
        for pair in pairs
        if len(pair) == 2
        for first, second in [pair]
        if first.distance < ratio_threshold * second.distance
    ]
    good.sort(key=lambda match: match.distance)
    return FeatureMatches(
        keypoints1=list(keypoints1),
        keypoints2=list(keypoints2),
        descriptors1=descriptors1,
        descriptors2=descriptors2,
        matches=good[:max_matches],
    )


FEATURE_MATCH_SPEC = OperationSpec(
    name="feature_match",
    display_name="Feature Matching",
    category=OperationCategory.MATCHING,
    inputs=[
        InputSlotSpec(name="image1", kind=InputKind.IMAGE),
        InputSlotSpec(name="image2", kind=InputKind.IMAGE),
    ],
    parameters={
        "algorithm": CategoryParameterSpec(
            title="Feature Algorithm",
            choices=[
                CategoryChoice(value="orb", label="ORB"),
                CategoryChoice(value="sift", label="SIFT"),
            ],
            default="orb",
        ),
        "matcher": CategoryParameterSpec(
            title="Matcher",
            choices=[
                CategoryChoice(value="bf", label="Brute Force"),
                CategoryChoice(value="flann", label="FLANN"),
            ],
            default="bf",
        ),
        "max_features": DiscreteParameterSpec(
            title="Maximum Features", min_value=10, max_value=20000, default=2000
        ),
        "ratio_threshold": ContinuousParameterSpec(
            title="Lowe Ratio Threshold", min_value=0.1, max_value=0.99, default=0.75
        ),
        "max_matches": DiscreteParameterSpec(
            title="Maximum Matches", min_value=1, max_value=10000, default=200
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="matches", kind=OutputKind.METRICS),
    ],
)


def feature_match_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image1: ImageData = inputs["image1"]
    image2: ImageData = inputs["image2"]
    ensure_pixel_budget(
        pixels=image1.width * image1.height + image2.width * image2.height,
        operation="feature_match",
        max_pixels=24_000_000,
    )
    result = extract_and_match(
        image1,
        image2,
        algorithm=params["algorithm"],
        matcher_name=params["matcher"],
        max_features=params["max_features"],
        ratio_threshold=params["ratio_threshold"],
        max_matches=params["max_matches"],
    )
    rendered = cv2.drawMatches(
        to_gray_u8(image1),
        result.keypoints1,
        to_gray_u8(image2),
        result.keypoints2,
        result.matches,
        None,
        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
    )
    records = [
        {
            "query_index": int(match.queryIdx),
            "train_index": int(match.trainIdx),
            "distance": float(match.distance),
            "query_point": [
                float(result.keypoints1[match.queryIdx].pt[0]),
                float(result.keypoints1[match.queryIdx].pt[1]),
            ],
            "train_point": [
                float(result.keypoints2[match.trainIdx].pt[0]),
                float(result.keypoints2[match.trainIdx].pt[1]),
            ],
        }
        for match in result.matches
    ]
    return OperationOutput(
        images={
            "image": as_image(
                rendered,
                source=image1,
                color_space=ColorSpace.BGR,
                name="feature_matches",
            )
        },
        data={
            "matches": {
                "count": len(records),
                "algorithm": params["algorithm"],
                "matcher": params["matcher"],
                "items": records,
            }
        },
    )
