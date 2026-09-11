from __future__ import annotations

from typing import TYPE_CHECKING

from .adjustment import (
    ADJUST_COLOR_SPEC,
    ADJUST_TONE_SPEC,
    APPLY_3D_LUT_SPEC,
    APPLY_LUT_SPEC,
    INVERT_SPEC,
    adjust_color_handler,
    adjust_tone_handler,
    apply_3d_lut_handler,
    apply_lut_handler,
    invert_handler,
)
from .annotation import DRAW_ANNOTATIONS_SPEC, draw_annotations_handler
from .classification import MODEL_PREDICT_SPEC, model_predict_handler
from .color import (
    COLOR_QUANTIZATION_SPEC,
    CONVERT_COLOR_SPEC,
    color_quantization_handler,
    convert_color_handler,
)
from .contour import FIND_CONTOURS_SPEC, find_contours_handler
from .compositing import (
    APPLY_MASK_SPEC,
    BITWISE_OPERATION_SPEC,
    BLEND_IMAGES_SPEC,
    IMAGE_ARITHMETIC_SPEC,
    WEIGHTED_SUM_SPEC,
    apply_mask_handler,
    bitwise_operation_handler,
    blend_images_handler,
    image_arithmetic_handler,
    weighted_sum_handler,
)
from .detection import (
    HOUGH_CIRCLES_SPEC,
    HOUGH_LINES_P_SPEC,
    hough_circles_handler,
    hough_lines_p_handler,
)
from .filtering import (
    BILATERAL_FILTER_SPEC,
    BOX_BLUR_SPEC,
    FILTER_2D_SPEC,
    GAUSSIAN_BLUR_SPEC,
    MEDIAN_BLUR_SPEC,
    bilateral_filter_handler,
    box_blur_handler,
    filter_2d_handler,
    gaussian_blur_handler,
    median_blur_handler,
)
from .geometry import (
    FLIP_SPEC,
    RESIZE_SPEC,
    ROTATE_SPEC,
    WARP_AFFINE_SPEC,
    WARP_PERSPECTIVE_SPEC,
    flip_handler,
    resize_handler,
    rotate_handler,
    warp_affine_handler,
    warp_perspective_handler,
)
from .gradient import (
    CANNY_SPEC,
    LAPLACIAN_SPEC,
    SCHARR_SPEC,
    SOBEL_SPEC,
    canny_handler,
    laplacian_handler,
    scharr_handler,
    sobel_handler,
)
from .histogram import (
    CLAHE_SPEC,
    EQUALIZE_HISTOGRAM_SPEC,
    HISTOGRAM_SPEC,
    clahe_handler,
    equalize_histogram_handler,
    histogram_handler,
)
from .feature import (
    BRIEF_DESCRIPTOR_SPEC,
    FAST_KEYPOINTS_SPEC,
    HARRIS_CORNERS_SPEC,
    HOG_DESCRIPTOR_SPEC,
    ORB_FEATURES_SPEC,
    SHI_TOMASI_CORNERS_SPEC,
    SIFT_FEATURES_SPEC,
    SURF_FEATURES_SPEC,
    brief_descriptor_handler,
    fast_keypoints_handler,
    harris_corners_handler,
    hog_descriptor_handler,
    orb_features_handler,
    shi_tomasi_corners_handler,
    sift_features_handler,
    surf_features_handler,
)
from .effects import (
    ADD_GRAIN_SPEC,
    VIGNETTE_SPEC,
    add_grain_handler,
    vignette_handler,
)
from .matching import (
    FEATURE_MATCH_SPEC,
    TEMPLATE_MATCH_SPEC,
    feature_match_handler,
    template_match_handler,
)
from .morphology import MORPHOLOGY_SPEC, morphology_handler
from .photo import (
    COLOR_CHANGE_SPEC,
    DETAIL_ENHANCE_SPEC,
    EDGE_PRESERVING_FILTER_SPEC,
    ILLUMINATION_CHANGE_SPEC,
    PENCIL_SKETCH_SPEC,
    SEAMLESS_CLONE_SPEC,
    STYLIZATION_SPEC,
    TEXTURE_FLATTENING_SPEC,
    color_change_handler,
    detail_enhance_handler,
    edge_preserving_filter_handler,
    illumination_change_handler,
    pencil_sketch_handler,
    seamless_clone_handler,
    stylization_handler,
    texture_flattening_handler,
)
from .registration import (
    ESTIMATE_HOMOGRAPHY_SPEC,
    LOCALIZE_PLANAR_OBJECT_SPEC,
    estimate_homography_handler,
    localize_planar_object_handler,
)
from .segmentation import (
    GRABCUT_SPEC,
    KMEANS_SEGMENTATION_SPEC,
    WATERSHED_SPEC,
    grabcut_handler,
    kmeans_segmentation_handler,
    watershed_handler,
)
from .threshold import (
    ADAPTIVE_THRESHOLD_SPEC,
    GLOBAL_THRESHOLD_SPEC,
    adaptive_threshold_handler,
    global_threshold_handler,
)
from .transform import (
    DFT_SPECTRUM_SPEC,
    PYRAMID_SPEC,
    dft_spectrum_handler,
    pyramid_handler,
)

if TYPE_CHECKING:
    from src.registry import OperationRegistry


def register_builtin_operations(
    registry: OperationRegistry,
) -> None:
    operations = [
        (ADJUST_TONE_SPEC, adjust_tone_handler),
        (ADJUST_COLOR_SPEC, adjust_color_handler),
        (APPLY_LUT_SPEC, apply_lut_handler),
        (APPLY_3D_LUT_SPEC, apply_3d_lut_handler),
        (INVERT_SPEC, invert_handler),
        (DRAW_ANNOTATIONS_SPEC, draw_annotations_handler),
        (MODEL_PREDICT_SPEC, model_predict_handler),
        (CONVERT_COLOR_SPEC, convert_color_handler),
        (COLOR_QUANTIZATION_SPEC, color_quantization_handler),
        (GLOBAL_THRESHOLD_SPEC, global_threshold_handler),
        (ADAPTIVE_THRESHOLD_SPEC, adaptive_threshold_handler),
        (GAUSSIAN_BLUR_SPEC, gaussian_blur_handler),
        (FILTER_2D_SPEC, filter_2d_handler),
        (BOX_BLUR_SPEC, box_blur_handler),
        (MEDIAN_BLUR_SPEC, median_blur_handler),
        (BILATERAL_FILTER_SPEC, bilateral_filter_handler),
        (MORPHOLOGY_SPEC, morphology_handler),
        (CANNY_SPEC, canny_handler),
        (SOBEL_SPEC, sobel_handler),
        (SCHARR_SPEC, scharr_handler),
        (LAPLACIAN_SPEC, laplacian_handler),
        (RESIZE_SPEC, resize_handler),
        (ROTATE_SPEC, rotate_handler),
        (FLIP_SPEC, flip_handler),
        (WARP_AFFINE_SPEC, warp_affine_handler),
        (WARP_PERSPECTIVE_SPEC, warp_perspective_handler),
        (HISTOGRAM_SPEC, histogram_handler),
        (EQUALIZE_HISTOGRAM_SPEC, equalize_histogram_handler),
        (CLAHE_SPEC, clahe_handler),
        (FIND_CONTOURS_SPEC, find_contours_handler),
        (BLEND_IMAGES_SPEC, blend_images_handler),
        (APPLY_MASK_SPEC, apply_mask_handler),
        (IMAGE_ARITHMETIC_SPEC, image_arithmetic_handler),
        (WEIGHTED_SUM_SPEC, weighted_sum_handler),
        (BITWISE_OPERATION_SPEC, bitwise_operation_handler),
        (VIGNETTE_SPEC, vignette_handler),
        (ADD_GRAIN_SPEC, add_grain_handler),
        (EDGE_PRESERVING_FILTER_SPEC, edge_preserving_filter_handler),
        (DETAIL_ENHANCE_SPEC, detail_enhance_handler),
        (PENCIL_SKETCH_SPEC, pencil_sketch_handler),
        (STYLIZATION_SPEC, stylization_handler),
        (COLOR_CHANGE_SPEC, color_change_handler),
        (ILLUMINATION_CHANGE_SPEC, illumination_change_handler),
        (TEXTURE_FLATTENING_SPEC, texture_flattening_handler),
        (SEAMLESS_CLONE_SPEC, seamless_clone_handler),
        (HARRIS_CORNERS_SPEC, harris_corners_handler),
        (SHI_TOMASI_CORNERS_SPEC, shi_tomasi_corners_handler),
        (FAST_KEYPOINTS_SPEC, fast_keypoints_handler),
        (SIFT_FEATURES_SPEC, sift_features_handler),
        (SURF_FEATURES_SPEC, surf_features_handler),
        (BRIEF_DESCRIPTOR_SPEC, brief_descriptor_handler),
        (ORB_FEATURES_SPEC, orb_features_handler),
        (HOG_DESCRIPTOR_SPEC, hog_descriptor_handler),
        (WATERSHED_SPEC, watershed_handler),
        (GRABCUT_SPEC, grabcut_handler),
        (KMEANS_SEGMENTATION_SPEC, kmeans_segmentation_handler),
        (HOUGH_LINES_P_SPEC, hough_lines_p_handler),
        (HOUGH_CIRCLES_SPEC, hough_circles_handler),
        (DFT_SPECTRUM_SPEC, dft_spectrum_handler),
        (PYRAMID_SPEC, pyramid_handler),
        (TEMPLATE_MATCH_SPEC, template_match_handler),
        (FEATURE_MATCH_SPEC, feature_match_handler),
        (ESTIMATE_HOMOGRAPHY_SPEC, estimate_homography_handler),
        (LOCALIZE_PLANAR_OBJECT_SPEC, localize_planar_object_handler),
    ]

    for spec, handler in operations:
        registry.register(spec=spec, handler=handler)
