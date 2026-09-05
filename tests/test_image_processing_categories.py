from collections import Counter

import cv2
import numpy as np
import pytest

from src.registry import create_default_registry
from src.schemas import ColorSpace, ImageData


@pytest.fixture
def registry():
    return create_default_registry()


@pytest.fixture
def gray_image():
    data = np.zeros((96, 128), dtype=np.uint8)
    cv2.rectangle(data, (15, 20), (60, 70), 180, -1)
    cv2.circle(data, (92, 48), 20, 255, 3)
    return ImageData(data=data, color_space=ColorSpace.GRAY, name="gray")


@pytest.fixture
def binary_image(gray_image):
    _, data = cv2.threshold(gray_image.data, 100, 255, cv2.THRESH_BINARY)
    return ImageData(data=data, color_space=ColorSpace.BINARY, name="binary")


@pytest.fixture
def bgr_image(gray_image):
    data = cv2.cvtColor(gray_image.data, cv2.COLOR_GRAY2BGR)
    data[30:65, 35:75] = (40, 180, 230)
    return ImageData(data=data, color_space=ColorSpace.BGR, name="bgr")


def assert_success(result):
    assert result.success is True, result.error


def test_registry_exposes_exactly_requested_categories(registry):
    categories = Counter(
        spec.category.value
        for spec in registry.list_specs()
    )

    assert len(registry.list_specs()) == 64
    assert set(categories) == {
        "adjustment",
        "annotation",
        "color",
        "classification",
        "compositing",
        "threshold",
        "filtering",
        "morphology",
        "gradient",
        "geometry",
        "histogram",
        "contour",
        "segmentation",
        "detection",
        "transform",
        "matching",
        "feature",
        "registration",
        "effects",
    }


def test_color_conversion(registry, bgr_image):
    hsv = registry.execute(
        operation="convert_color",
        inputs={"image": bgr_image},
        params={"target_color_space": "hsv"},
    )
    assert_success(hsv)
    assert hsv.output.images["image"].color_space == ColorSpace.HSV

    gray = registry.execute(
        operation="convert_color",
        inputs={"image": hsv.output.images["image"]},
        params={"target_color_space": "gray"},
    )
    assert_success(gray)
    assert gray.output.images["image"].shape == (96, 128)


def test_threshold_operations(registry, gray_image):
    global_result = registry.execute(
        operation="global_threshold",
        inputs={"image": gray_image},
        params={"threshold": 100},
    )
    assert_success(global_result)
    assert global_result.output.images["image"].color_space == ColorSpace.BINARY
    assert global_result.output.data["threshold"] == 100.0

    adaptive = registry.execute(
        operation="adaptive_threshold",
        inputs={"image": gray_image},
        params={"block_size": 11},
    )
    assert_success(adaptive)
    assert adaptive.output.images["image"].shape == gray_image.shape


@pytest.mark.parametrize(
    "operation",
    ["box_blur", "median_blur", "bilateral_filter"],
)
def test_filtering_operations(registry, bgr_image, operation):
    result = registry.execute(
        operation=operation,
        inputs={"image": bgr_image},
    )
    assert_success(result)
    assert result.output.images["image"].shape == bgr_image.shape


def test_custom_filter_accepts_json_style_kernel(registry, gray_image):
    result = registry.execute(
        operation="filter_2d",
        inputs={
            "image": gray_image,
            "kernel": [
                [0.0, -1.0, 0.0],
                [-1.0, 5.0, -1.0],
                [0.0, -1.0, 0.0],
            ],
        },
    )
    assert_success(result)
    assert result.output.images["image"].shape == gray_image.shape


def test_morphology_operation(registry, binary_image):
    result = registry.execute(
        operation="morphology",
        inputs={"image": binary_image},
        params={
            "operation": "close",
            "kernel_shape": "ellipse",
            "kernel_size": 5,
        },
    )
    assert_success(result)
    assert result.output.images["image"].color_space == ColorSpace.BINARY


@pytest.mark.parametrize("operation", ["sobel", "scharr", "laplacian"])
def test_gradient_operations(registry, gray_image, operation):
    result = registry.execute(
        operation=operation,
        inputs={"image": gray_image},
    )
    assert_success(result)
    assert result.output.images["image"].dtype == "uint8"
    assert result.output.images["image"].shape == gray_image.shape


def test_geometry_operations(registry, bgr_image):
    flip = registry.execute(
        operation="flip",
        inputs={"image": bgr_image},
        params={"direction": "vertical"},
    )
    assert_success(flip)

    rotate = registry.execute(
        operation="rotate",
        inputs={"image": bgr_image},
        params={"angle": 30.0, "expand": True},
    )
    assert_success(rotate)
    assert rotate.output.images["image"].width > bgr_image.width

    source3 = [[0, 0], [127, 0], [0, 95]]
    target3 = [[5, 4], [120, 2], [7, 90]]
    affine = registry.execute(
        operation="warp_affine",
        inputs={
            "image": bgr_image,
            "source_points": source3,
            "destination_points": target3,
        },
        params={"width": 128, "height": 96},
    )
    assert_success(affine)
    assert affine.output.images["image"].shape == bgr_image.shape

    source4 = [[0, 0], [127, 0], [127, 95], [0, 95]]
    target4 = [[4, 3], [122, 5], [125, 92], [3, 90]]
    perspective = registry.execute(
        operation="warp_perspective",
        inputs={
            "image": bgr_image,
            "source_points": source4,
            "destination_points": target4,
        },
        params={"width": 128, "height": 96},
    )
    assert_success(perspective)


def test_histogram_operations(registry, gray_image):
    histogram = registry.execute(
        operation="histogram",
        inputs={"image": gray_image},
        params={"bins": 32, "normalize": True},
    )
    assert_success(histogram)
    values = histogram.output.data["histogram"]
    assert values.shape == (32,)
    assert float(values.sum()) == pytest.approx(1.0)

    equalized = registry.execute(
        operation="equalize_histogram",
        inputs={"image": gray_image},
    )
    assert_success(equalized)

    clahe = registry.execute(
        operation="clahe",
        inputs={"image": gray_image},
    )
    assert_success(clahe)


def test_contour_operation(registry, binary_image):
    result = registry.execute(
        operation="find_contours",
        inputs={"image": binary_image},
        params={"min_area": 20.0},
    )
    assert_success(result)
    assert len(result.output.data["contours"]) >= 1
    assert result.output.images["image"].color_space == ColorSpace.BGR
    assert result.output.data["features"][0]["area"] > 0


def test_segmentation_operations(registry, bgr_image):
    watershed = registry.execute(
        operation="watershed",
        inputs={"image": bgr_image},
    )
    assert_success(watershed)
    assert watershed.output.images["labels"].dtype == "int32"

    grabcut = registry.execute(
        operation="grabcut",
        inputs={"image": bgr_image},
        params={"x": 5, "y": 5, "width": 115, "height": 85},
    )
    assert_success(grabcut)
    assert grabcut.output.images["mask"].color_space == ColorSpace.BINARY


def test_detection_operations(registry, gray_image, binary_image):
    lines = registry.execute(
        operation="hough_lines_p",
        inputs={"image": binary_image},
        params={"threshold": 15, "min_line_length": 10.0},
    )
    assert_success(lines)
    assert lines.output.data["lines"].shape[1] == 4

    circles = registry.execute(
        operation="hough_circles",
        inputs={"image": gray_image},
        params={"accumulator_threshold": 10.0},
    )
    assert_success(circles)
    assert circles.output.data["circles"].shape[1] == 3


def test_transform_operations(registry, gray_image):
    spectrum = registry.execute(
        operation="dft_spectrum",
        inputs={"image": gray_image},
    )
    assert_success(spectrum)
    assert spectrum.output.images["image"].dtype == "uint8"

    pyramid = registry.execute(
        operation="image_pyramid",
        inputs={"image": gray_image},
        params={"direction": "down", "levels": 2},
    )
    assert_success(pyramid)
    assert pyramid.output.images["image"].shape == (24, 32)


def test_template_matching(registry, gray_image):
    template = ImageData(
        data=gray_image.data[15:76, 10:66].copy(),
        color_space=ColorSpace.GRAY,
        name="template",
    )
    result = registry.execute(
        operation="template_match",
        inputs={"image": gray_image, "template": template},
    )
    assert_success(result)
    best = result.output.data["best_match"]
    assert best["top_left"] == [10, 15]
    assert result.output.images["response"].dtype == "float32"
