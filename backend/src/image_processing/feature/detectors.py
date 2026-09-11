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

from ..common import as_image, ensure_pixel_budget, to_bgr
from .common import (
    draw_keypoints,
    empty_descriptors,
    serialize_keypoints,
    to_gray_u8,
)


_IMAGE_INPUT = InputSlotSpec(name="image", kind=InputKind.IMAGE)
_KEYPOINT_OUTPUTS = [
    OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
    OutputSlotSpec(name="keypoints", kind=OutputKind.METRICS),
]
_FEATURE_OUTPUTS = [
    *_KEYPOINT_OUTPUTS,
    OutputSlotSpec(name="descriptors", kind=OutputKind.ARRAY),
]
_BOOL_CHOICES = [
    CategoryChoice(value=False, label="Disabled"),
    CategoryChoice(value=True, label="Enabled"),
]


HARRIS_CORNERS_SPEC = OperationSpec(
    name="harris_corners",
    display_name="Harris Corners",
    category=OperationCategory.FEATURE,
    inputs=[_IMAGE_INPUT],
    parameters={
        "block_size": DiscreteParameterSpec(
            title="Block Size", min_value=2, max_value=31, default=2
        ),
        "aperture_size": DiscreteParameterSpec(
            title="Sobel Aperture", values=[3, 5, 7], default=3
        ),
        "k": ContinuousParameterSpec(
            title="Harris K", min_value=0.01, max_value=0.2, default=0.04
        ),
        "threshold_ratio": ContinuousParameterSpec(
            title="Response Threshold Ratio",
            min_value=0.0001,
            max_value=1.0,
            default=0.01,
        ),
        "max_keypoints": DiscreteParameterSpec(
            title="Maximum Keypoints", min_value=1, max_value=10000, default=1000
        ),
        "subpixel_refinement": CategoryParameterSpec(
            title="Subpixel Refinement", choices=_BOOL_CHOICES, default=True
        ),
    },
    outputs=[
        *_KEYPOINT_OUTPUTS,
        OutputSlotSpec(name="response", kind=OutputKind.IMAGE),
    ],
)


SHI_TOMASI_CORNERS_SPEC = OperationSpec(
    name="shi_tomasi_corners",
    display_name="Shi-Tomasi Corners",
    category=OperationCategory.FEATURE,
    inputs=[_IMAGE_INPUT],
    parameters={
        "max_corners": DiscreteParameterSpec(
            title="Maximum Corners", min_value=1, max_value=10000, default=500
        ),
        "quality_level": ContinuousParameterSpec(
            title="Quality Level", min_value=0.0001, max_value=1.0, default=0.01
        ),
        "min_distance": ContinuousParameterSpec(
            title="Minimum Distance", min_value=0.0, max_value=10000.0, default=10.0
        ),
        "block_size": DiscreteParameterSpec(
            title="Block Size", min_value=2, max_value=31, default=3
        ),
    },
    outputs=_KEYPOINT_OUTPUTS,
)


FAST_KEYPOINTS_SPEC = OperationSpec(
    name="fast_keypoints",
    display_name="FAST Keypoints",
    category=OperationCategory.FEATURE,
    inputs=[_IMAGE_INPUT],
    parameters={
        "threshold": DiscreteParameterSpec(
            title="Threshold", min_value=1, max_value=255, default=10
        ),
        "nonmax_suppression": CategoryParameterSpec(
            title="Non-maximum Suppression", choices=_BOOL_CHOICES, default=True
        ),
        "detector_type": CategoryParameterSpec(
            title="Detector Type",
            choices=[
                CategoryChoice(value="5_8", label="5-8"),
                CategoryChoice(value="7_12", label="7-12"),
                CategoryChoice(value="9_16", label="9-16"),
            ],
            default="9_16",
        ),
        "max_keypoints": DiscreteParameterSpec(
            title="Maximum Keypoints", min_value=1, max_value=50000, default=5000
        ),
    },
    outputs=_KEYPOINT_OUTPUTS,
)


SIFT_FEATURES_SPEC = OperationSpec(
    name="sift_features",
    display_name="SIFT Features",
    category=OperationCategory.FEATURE,
    inputs=[_IMAGE_INPUT],
    parameters={
        "max_features": DiscreteParameterSpec(
            title="Maximum Features", min_value=1, max_value=10000, default=1000
        ),
        "octave_layers": DiscreteParameterSpec(
            title="Octave Layers", min_value=1, max_value=10, default=3
        ),
        "contrast_threshold": ContinuousParameterSpec(
            title="Contrast Threshold", min_value=0.0001, max_value=1.0, default=0.04
        ),
        "edge_threshold": ContinuousParameterSpec(
            title="Edge Threshold", min_value=0.1, max_value=100.0, default=10.0
        ),
        "sigma": ContinuousParameterSpec(
            title="Sigma", min_value=0.1, max_value=10.0, default=1.6
        ),
    },
    outputs=_FEATURE_OUTPUTS,
)


SURF_FEATURES_SPEC = OperationSpec(
    name="surf_features",
    display_name="SURF Features (Optional)",
    category=OperationCategory.FEATURE,
    description="opencv-contrib 및 nonfree 빌드가 필요합니다.",
    inputs=[_IMAGE_INPUT],
    parameters={
        "hessian_threshold": ContinuousParameterSpec(
            title="Hessian Threshold", min_value=1.0, max_value=100000.0, default=400.0
        ),
        "octaves": DiscreteParameterSpec(
            title="Octaves", min_value=1, max_value=10, default=4
        ),
        "octave_layers": DiscreteParameterSpec(
            title="Octave Layers", min_value=1, max_value=10, default=3
        ),
        "extended": CategoryParameterSpec(
            title="128-element Descriptor", choices=_BOOL_CHOICES, default=False
        ),
        "upright": CategoryParameterSpec(
            title="Upright", choices=_BOOL_CHOICES, default=False
        ),
        "max_features": DiscreteParameterSpec(
            title="Maximum Features", min_value=1, max_value=10000, default=2000
        ),
    },
    outputs=_FEATURE_OUTPUTS,
)


BRIEF_DESCRIPTOR_SPEC = OperationSpec(
    name="brief_descriptors",
    display_name="FAST + BRIEF Descriptors (Optional)",
    category=OperationCategory.FEATURE,
    description="FAST keypoint를 검출한 뒤 opencv-contrib BRIEF를 계산합니다.",
    inputs=[_IMAGE_INPUT],
    parameters={
        "fast_threshold": DiscreteParameterSpec(
            title="FAST Threshold", min_value=1, max_value=255, default=10
        ),
        "bytes": DiscreteParameterSpec(
            title="Descriptor Bytes", values=[16, 32, 64], default=32
        ),
        "use_orientation": CategoryParameterSpec(
            title="Use Orientation", choices=_BOOL_CHOICES, default=False
        ),
        "max_features": DiscreteParameterSpec(
            title="Maximum Features", min_value=1, max_value=50000, default=5000
        ),
    },
    outputs=_FEATURE_OUTPUTS,
)


ORB_FEATURES_SPEC = OperationSpec(
    name="orb_features",
    display_name="ORB Features",
    category=OperationCategory.FEATURE,
    inputs=[_IMAGE_INPUT],
    parameters={
        "max_features": DiscreteParameterSpec(
            title="Maximum Features", min_value=1, max_value=50000, default=1000
        ),
        "scale_factor": ContinuousParameterSpec(
            title="Scale Factor", min_value=1.01, max_value=3.0, default=1.2
        ),
        "levels": DiscreteParameterSpec(
            title="Pyramid Levels", min_value=1, max_value=16, default=8
        ),
        "edge_threshold": DiscreteParameterSpec(
            title="Edge Threshold", min_value=1, max_value=128, default=31
        ),
        "fast_threshold": DiscreteParameterSpec(
            title="FAST Threshold", min_value=0, max_value=255, default=20
        ),
    },
    outputs=_FEATURE_OUTPUTS,
)


HOG_DESCRIPTOR_SPEC = OperationSpec(
    name="hog_descriptor",
    display_name="HOG Descriptor",
    category=OperationCategory.FEATURE,
    inputs=[_IMAGE_INPUT],
    parameters={
        "width": DiscreteParameterSpec(
            title="Window Width", min_value=16, max_value=2048, default=64
        ),
        "height": DiscreteParameterSpec(
            title="Window Height", min_value=16, max_value=2048, default=64
        ),
        "cell_size": DiscreteParameterSpec(
            title="Cell Size", values=[4, 8, 16, 32], default=8
        ),
        "block_cells": DiscreteParameterSpec(
            title="Block Cells", values=[2, 3, 4], default=2
        ),
        "bins": DiscreteParameterSpec(
            title="Orientation Bins", min_value=4, max_value=32, default=9
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="descriptor", kind=OutputKind.ARRAY),
    ],
)


def _budget(image: ImageData, operation: str) -> np.ndarray:
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation=operation,
        max_pixels=16_000_000,
    )
    return to_gray_u8(image)


def harris_corners_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    gray = _budget(image, "harris_corners")
    response = cv2.cornerHarris(
        np.float32(gray), params["block_size"], params["aperture_size"], params["k"]
    )
    maximum = float(response.max()) if response.size else 0.0
    local_max = response == cv2.dilate(response, None)
    mask = local_max & (response > params["threshold_ratio"] * maximum)
    coordinates = np.argwhere(mask)
    if coordinates.size:
        scores = response[coordinates[:, 0], coordinates[:, 1]]
        order = np.argsort(scores)[::-1][: params["max_keypoints"]]
        coordinates = coordinates[order]
    points = np.flip(coordinates, axis=1).astype(np.float32).reshape(-1, 1, 2)
    if params["subpixel_refinement"] and len(points):
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
        cv2.cornerSubPix(gray, points, (5, 5), (-1, -1), criteria)
    keypoints = [cv2.KeyPoint(float(x), float(y), 3.0) for x, y in points.reshape(-1, 2)]
    annotated = draw_keypoints(image, keypoints)
    return OperationOutput(
        images={
            "image": as_image(annotated, source=image, color_space=ColorSpace.BGR),
            "response": as_image(
                response, source=image, color_space=ColorSpace.GRAY, name="harris_response"
            ),
        },
        data={"keypoints": serialize_keypoints(keypoints)},
    )


def shi_tomasi_corners_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    gray = _budget(image, "shi_tomasi_corners")
    corners = cv2.goodFeaturesToTrack(
        gray,
        maxCorners=params["max_corners"],
        qualityLevel=params["quality_level"],
        minDistance=params["min_distance"],
        blockSize=params["block_size"],
    )
    coordinates = np.empty((0, 2), np.float32) if corners is None else corners.reshape(-1, 2)
    keypoints = [cv2.KeyPoint(float(x), float(y), 3.0) for x, y in coordinates]
    annotated = draw_keypoints(image, keypoints)
    return OperationOutput(
        images={"image": as_image(annotated, source=image, color_space=ColorSpace.BGR)},
        data={"keypoints": serialize_keypoints(keypoints)},
    )


def fast_keypoints_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    gray = _budget(image, "fast_keypoints")
    detector_types = {
        "5_8": cv2.FAST_FEATURE_DETECTOR_TYPE_5_8,
        "7_12": cv2.FAST_FEATURE_DETECTOR_TYPE_7_12,
        "9_16": cv2.FAST_FEATURE_DETECTOR_TYPE_9_16,
    }
    detector = cv2.FastFeatureDetector_create(
        threshold=params["threshold"],
        nonmaxSuppression=params["nonmax_suppression"],
        type=detector_types[params["detector_type"]],
    )
    keypoints = sorted(detector.detect(gray, None), key=lambda x: x.response, reverse=True)[
        : params["max_keypoints"]
    ]
    annotated = draw_keypoints(image, keypoints)
    return OperationOutput(
        images={"image": as_image(annotated, source=image, color_space=ColorSpace.BGR)},
        data={"keypoints": serialize_keypoints(keypoints)},
    )


def _feature_output(image: ImageData, keypoints, descriptors, columns: int, dtype):
    keypoints = list(keypoints or [])
    if descriptors is None:
        descriptors = empty_descriptors(columns, dtype=dtype)
    annotated = draw_keypoints(image, keypoints, rich=True)
    return OperationOutput(
        images={"image": as_image(annotated, source=image, color_space=ColorSpace.BGR)},
        data={
            "keypoints": serialize_keypoints(keypoints),
            "descriptors": np.ascontiguousarray(descriptors),
        },
    )


def sift_features_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    gray = _budget(image, "sift_features")
    detector = cv2.SIFT_create(
        nfeatures=params["max_features"],
        nOctaveLayers=params["octave_layers"],
        contrastThreshold=params["contrast_threshold"],
        edgeThreshold=params["edge_threshold"],
        sigma=params["sigma"],
    )
    keypoints, descriptors = detector.detectAndCompute(gray, None)
    return _feature_output(image, keypoints, descriptors, 128, np.float32)


def surf_features_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    gray = _budget(image, "surf_features")
    xfeatures = getattr(cv2, "xfeatures2d", None)
    factory = getattr(xfeatures, "SURF_create", None) if xfeatures is not None else None
    if factory is None:
        raise OperationExecutionError(
            code="optional_dependency_unavailable",
            message="SURF requires an OpenCV contrib build with nonfree enabled",
            details={"dependency": "opencv-contrib/nonfree"},
        )
    try:
        detector = factory(
            hessianThreshold=params["hessian_threshold"],
            nOctaves=params["octaves"],
            nOctaveLayers=params["octave_layers"],
            extended=params["extended"],
            upright=params["upright"],
        )
    except cv2.error as exc:
        raise OperationExecutionError(
            code="optional_dependency_unavailable",
            message="SURF is unavailable in this OpenCV build",
            details={"dependency": "opencv-contrib/nonfree"},
        ) from exc
    keypoints, descriptors = detector.detectAndCompute(gray, None)
    order = np.argsort([point.response for point in keypoints])[::-1][
        : params["max_features"]
    ]
    selected = [keypoints[int(index)] for index in order]
    descriptors = None if descriptors is None else descriptors[order]
    columns = 128 if params["extended"] else 64
    return _feature_output(image, selected, descriptors, columns, np.float32)


def brief_descriptor_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    gray = _budget(image, "brief_descriptors")
    xfeatures = getattr(cv2, "xfeatures2d", None)
    factory = (
        getattr(xfeatures, "BriefDescriptorExtractor_create", None)
        if xfeatures is not None
        else None
    )
    if factory is None:
        raise OperationExecutionError(
            code="optional_dependency_unavailable",
            message="BRIEF requires opencv-contrib-python",
            details={"dependency": "opencv-contrib-python"},
        )
    fast = cv2.FastFeatureDetector_create(
        threshold=params["fast_threshold"], nonmaxSuppression=True
    )
    keypoints = sorted(fast.detect(gray, None), key=lambda x: x.response, reverse=True)[
        : params["max_features"]
    ]
    extractor = factory(bytes=params["bytes"], use_orientation=params["use_orientation"])
    keypoints, descriptors = extractor.compute(gray, keypoints)
    return _feature_output(
        image, keypoints, descriptors, params["bytes"], np.uint8
    )


def orb_features_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    gray = _budget(image, "orb_features")
    detector = cv2.ORB_create(
        nfeatures=params["max_features"],
        scaleFactor=params["scale_factor"],
        nlevels=params["levels"],
        edgeThreshold=params["edge_threshold"],
        fastThreshold=params["fast_threshold"],
    )
    keypoints, descriptors = detector.detectAndCompute(gray, None)
    return _feature_output(image, keypoints, descriptors, 32, np.uint8)


def hog_descriptor_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    gray = _budget(image, "hog_descriptor")
    width, height = params["width"], params["height"]
    cell = params["cell_size"]
    block_cells = params["block_cells"]
    block = cell * block_cells
    if width % cell or height % cell or width < block or height < block:
        raise OperationExecutionError(
            code="invalid_hog_geometry",
            message="width and height must be cell multiples and at least one block",
            details={"width": width, "height": height, "cell": cell, "block": block},
        )
    resized = cv2.resize(gray, (width, height), interpolation=cv2.INTER_AREA)
    descriptor = cv2.HOGDescriptor(
        (width, height),
        (block, block),
        (cell, cell),
        (cell, cell),
        params["bins"],
    ).compute(resized)
    return OperationOutput(
        images={
            "image": as_image(
                resized, source=image, color_space=ColorSpace.GRAY, name="hog_input"
            )
        },
        data={"descriptor": descriptor.reshape(1, -1).astype(np.float32)},
    )
