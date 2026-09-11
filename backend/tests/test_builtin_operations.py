import numpy as np
import pytest

pytest.importorskip("cv2")

from src.registry import create_default_registry
from src.schemas import ColorSpace, ImageData


def test_default_registry_contains_builtin_operations():
    registry = create_default_registry()

    assert [spec.name for spec in registry.list_specs()] == [
        "adaptive_threshold",
        "add_grain",
        "adjust_color",
        "adjust_tone",
        "apply_3d_lut",
        "apply_lut",
        "apply_mask",
        "bilateral_filter",
        "bitwise_operation",
        "blend_images",
        "box_blur",
        "brief_descriptors",
        "canny",
        "clahe",
        "color_change",
        "color_quantization",
        "convert_color",
        "detail_enhance",
        "dft_spectrum",
        "draw_annotations",
        "edge_preserving_filter",
        "equalize_histogram",
        "estimate_homography",
        "fast_keypoints",
        "feature_match",
        "filter_2d",
        "find_contours",
        "flip",
        "gaussian_blur",
        "global_threshold",
        "grabcut",
        "harris_corners",
        "histogram",
        "hog_descriptor",
        "hough_circles",
        "hough_lines_p",
        "illumination_change",
        "image_arithmetic",
        "image_pyramid",
        "invert",
        "kmeans_segmentation",
        "laplacian",
        "localize_planar_object",
        "median_blur",
        "model_predict",
        "morphology",
        "orb_features",
        "pencil_sketch",
        "resize",
        "rotate",
        "scharr",
        "seamless_clone",
        "shi_tomasi_corners",
        "sift_features",
        "sobel",
        "stylization",
        "surf_features",
        "template_match",
        "texture_flattening",
        "vignette",
        "warp_affine",
        "warp_perspective",
        "watershed",
        "weighted_sum",
    ]


def test_gaussian_blur_executes_end_to_end():
    registry = create_default_registry()
    image = ImageData(
        data=np.arange(64, dtype=np.uint8).reshape(8, 8),
        color_space=ColorSpace.GRAY,
        name="sample",
    )

    result = registry.execute(
        operation="gaussian_blur",
        inputs={"image": image},
        params={"kernel_size": 3},
    )

    assert result.success is True
    assert result.output.images["image"].shape == (8, 8)
    assert result.output.images["image"].name == "sample"


def test_canny_validates_input_and_threshold_relationship():
    registry = create_default_registry()
    bgr_image = ImageData(
        data=np.zeros((8, 8, 3), dtype=np.uint8),
        color_space=ColorSpace.BGR,
    )

    invalid_input = registry.execute(
        operation="canny",
        inputs={"image": bgr_image},
    )

    assert invalid_input.success is False
    assert invalid_input.error is not None
    assert invalid_input.error.code == "input_validation_error"

    gray_image = ImageData(
        data=np.zeros((8, 8), dtype=np.uint8),
        color_space=ColorSpace.GRAY,
    )
    invalid_threshold = registry.execute(
        operation="canny",
        inputs={"image": gray_image},
        params={"threshold_low": 200, "threshold_high": 100},
    )

    assert invalid_threshold.success is False
    assert invalid_threshold.error is not None
    assert invalid_threshold.error.code == "parameter_validation_error"


@pytest.mark.parametrize(
    ("params", "expected_shape"),
    [
        ({"width": 6, "height": 4}, (4, 6, 3)),
        ({"scale_x": 0.5, "scale_y": 0.5}, (4, 5, 3)),
    ],
)
def test_resize_supports_size_and_scale_modes(params, expected_shape):
    registry = create_default_registry()
    image = ImageData(
        data=np.zeros((8, 10, 3), dtype=np.uint8),
        color_space=ColorSpace.BGR,
    )

    result = registry.execute(
        operation="resize",
        inputs={"image": image},
        params=params,
    )

    assert result.success is True
    assert result.output.images["image"].shape == expected_shape


def test_resize_rejects_excessive_output_before_allocation():
    registry = create_default_registry()
    image = ImageData(
        data=np.zeros((1000, 1000), dtype=np.uint8),
        color_space=ColorSpace.GRAY,
    )

    result = registry.execute(
        operation="resize",
        inputs={"image": image},
        params={"scale_x": 10.0, "scale_y": 10.0},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "resource_limit_exceeded"
