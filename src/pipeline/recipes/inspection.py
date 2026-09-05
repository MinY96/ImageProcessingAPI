from src.pipeline.references import pipeline_input, step_output
from src.schemas import ColorSpace, PipelineSpec, PipelineStepSpec

from .common import gray_input, image_input, mask_input, photo_input


def _gray_step(source):
    return PipelineStepSpec(
        id="gray",
        operation="convert_color",
        inputs={"image": source},
        params={"target_color_space": "gray"},
    )


def create_inspection_recipes() -> list[PipelineSpec]:
    return [
        PipelineSpec(
            name="edge_thumbnail",
            display_name="Edge Thumbnail",
            description="이미지를 축소하고 Canny edge preview를 생성합니다.",
            inputs=[image_input()],
            steps=[
                _gray_step(pipeline_input("image")),
                PipelineStepSpec(
                    id="blur",
                    operation="gaussian_blur",
                    inputs={"image": step_output("gray")},
                    params={"kernel_size": 5},
                ),
                PipelineStepSpec(
                    id="resize",
                    operation="resize",
                    inputs={"image": step_output("blur")},
                    params={"width": 320, "height": 240},
                ),
                PipelineStepSpec(
                    id="edges",
                    operation="canny",
                    inputs={"image": step_output("resize")},
                    params={"threshold_low": 100, "threshold_high": 200},
                ),
            ],
            outputs={"edges": step_output("edges")},
        ),
        PipelineSpec(
            name="document_otsu",
            display_name="Document Cleanup (Otsu)",
            description="조명이 균일한 문서를 Otsu threshold와 close로 정리합니다.",
            inputs=[image_input()],
            steps=[
                _gray_step(pipeline_input("image")),
                PipelineStepSpec(
                    id="blur",
                    operation="gaussian_blur",
                    inputs={"image": step_output("gray")},
                    params={"kernel_size": 5, "sigma_x": 1.0},
                ),
                PipelineStepSpec(
                    id="threshold",
                    operation="global_threshold",
                    inputs={"image": step_output("blur")},
                    params={"mode": "binary", "use_otsu": True},
                ),
                PipelineStepSpec(
                    id="close",
                    operation="morphology",
                    inputs={"image": step_output("threshold")},
                    params={"operation": "close", "kernel_size": 3},
                ),
            ],
            outputs={"image": step_output("close")},
        ),
        PipelineSpec(
            name="document_adaptive",
            display_name="Document Cleanup (Adaptive)",
            description="그림자나 밝기 편차가 있는 문서를 adaptive threshold로 정리합니다.",
            inputs=[image_input()],
            steps=[
                _gray_step(pipeline_input("image")),
                PipelineStepSpec(
                    id="denoise",
                    operation="bilateral_filter",
                    inputs={"image": step_output("gray")},
                    params={"diameter": 7, "sigma_color": 50.0, "sigma_space": 50.0},
                ),
                PipelineStepSpec(
                    id="threshold",
                    operation="adaptive_threshold",
                    inputs={"image": step_output("denoise")},
                    params={"method": "gaussian", "mode": "binary", "block_size": 21, "c": 5.0},
                ),
                PipelineStepSpec(
                    id="open",
                    operation="morphology",
                    inputs={"image": step_output("threshold")},
                    params={"operation": "open", "kernel_size": 3},
                ),
                PipelineStepSpec(
                    id="close",
                    operation="morphology",
                    inputs={"image": step_output("open")},
                    params={"operation": "close", "kernel_size": 3},
                ),
            ],
            outputs={"image": step_output("close")},
        ),
        PipelineSpec(
            name="binary_mask_cleanup",
            display_name="Binary Mask Cleanup",
            description="작은 점을 제거하고 끊어진 전경을 연결합니다.",
            inputs=[mask_input()],
            steps=[
                PipelineStepSpec(
                    id="open",
                    operation="morphology",
                    inputs={"image": pipeline_input("mask")},
                    params={"operation": "open", "kernel_shape": "ellipse", "kernel_size": 3},
                ),
                PipelineStepSpec(
                    id="close",
                    operation="morphology",
                    inputs={"image": step_output("open")},
                    params={"operation": "close", "kernel_shape": "ellipse", "kernel_size": 5},
                ),
            ],
            outputs={"mask": step_output("close")},
        ),
        PipelineSpec(
            name="general_edge_detection",
            display_name="General Edge Detection",
            description="국부 대비 보정과 잡음 제거 후 연결된 Canny edge를 생성합니다.",
            inputs=[image_input()],
            steps=[
                _gray_step(pipeline_input("image")),
                PipelineStepSpec(
                    id="contrast",
                    operation="clahe",
                    inputs={"image": step_output("gray")},
                    params={"clip_limit": 2.0, "tile_grid_size": 8},
                ),
                PipelineStepSpec(
                    id="blur",
                    operation="gaussian_blur",
                    inputs={"image": step_output("contrast")},
                    params={"kernel_size": 5, "sigma_x": 1.0},
                ),
                PipelineStepSpec(
                    id="edges",
                    operation="canny",
                    inputs={"image": step_output("blur")},
                    params={"threshold_low": 50, "threshold_high": 150, "l2_gradient": True},
                ),
                PipelineStepSpec(
                    id="close",
                    operation="morphology",
                    inputs={"image": step_output("edges")},
                    params={"operation": "close", "kernel_size": 3},
                ),
            ],
            outputs={"edges": step_output("close")},
        ),
        PipelineSpec(
            name="sem_profile_edges",
            display_name="SEM Profile Edges",
            description="SEM 국부 대비와 경계를 강화해 profile 후보 mask를 생성합니다.",
            inputs=[image_input()],
            steps=[
                _gray_step(pipeline_input("image")),
                PipelineStepSpec(
                    id="contrast",
                    operation="clahe",
                    inputs={"image": step_output("gray")},
                    params={"clip_limit": 2.5, "tile_grid_size": 8},
                ),
                PipelineStepSpec(
                    id="denoise",
                    operation="bilateral_filter",
                    inputs={"image": step_output("contrast")},
                    params={"diameter": 5, "sigma_color": 35.0, "sigma_space": 35.0},
                ),
                PipelineStepSpec(
                    id="gradient",
                    operation="scharr",
                    inputs={"image": step_output("denoise")},
                    params={"direction": "x"},
                ),
                PipelineStepSpec(
                    id="threshold",
                    operation="global_threshold",
                    inputs={"image": step_output("gradient")},
                    params={"threshold": 40, "mode": "binary"},
                ),
                PipelineStepSpec(
                    id="close",
                    operation="morphology",
                    inputs={"image": step_output("threshold")},
                    params={"operation": "close", "kernel_shape": "rect", "kernel_size": 3},
                ),
            ],
            outputs={
                "profile_mask": step_output("close"),
                "gradient": step_output("gradient"),
            },
        ),
        PipelineSpec(
            name="reference_difference",
            display_name="Reference Difference Inspection",
            description="Reference와 Current 차이를 이진화하고 contour와 형상 지표를 반환합니다.",
            inputs=[
                image_input("reference", color_spaces=[ColorSpace.GRAY]),
                image_input("current", color_spaces=[ColorSpace.GRAY]),
            ],
            steps=[
                PipelineStepSpec(
                    id="difference",
                    operation="image_arithmetic",
                    inputs={
                        "image1": pipeline_input("reference"),
                        "image2": pipeline_input("current"),
                    },
                    params={"operation": "absolute_difference"},
                ),
                PipelineStepSpec(
                    id="blur",
                    operation="gaussian_blur",
                    inputs={"image": step_output("difference")},
                    params={"kernel_size": 3},
                ),
                PipelineStepSpec(
                    id="threshold",
                    operation="global_threshold",
                    inputs={"image": step_output("blur")},
                    params={"threshold": 20, "mode": "binary"},
                ),
                PipelineStepSpec(
                    id="clean",
                    operation="morphology",
                    inputs={"image": step_output("threshold")},
                    params={"operation": "open", "kernel_shape": "ellipse", "kernel_size": 3},
                ),
                PipelineStepSpec(
                    id="gray_mask",
                    operation="convert_color",
                    inputs={"image": step_output("clean")},
                    params={"target_color_space": "gray"},
                ),
                PipelineStepSpec(
                    id="binary_mask",
                    operation="global_threshold",
                    inputs={"image": step_output("gray_mask")},
                    params={"threshold": 127, "mode": "binary"},
                ),
                PipelineStepSpec(
                    id="contours",
                    operation="find_contours",
                    inputs={"image": step_output("binary_mask")},
                    params={"retrieval_mode": "external", "min_area": 4.0},
                ),
            ],
            outputs={
                "difference": step_output("difference"),
                "mask": step_output("binary_mask"),
                "annotated": step_output("contours", "image"),
                "contours": step_output("contours", "contours"),
                "features": step_output("contours", "features"),
            },
        ),
        PipelineSpec(
            name="line_detection",
            display_name="Line Detection",
            description="Canny edge에서 확률적 Hough line을 검출합니다.",
            inputs=[image_input()],
            steps=[
                _gray_step(pipeline_input("image")),
                PipelineStepSpec(
                    id="blur",
                    operation="gaussian_blur",
                    inputs={"image": step_output("gray")},
                    params={"kernel_size": 5},
                ),
                PipelineStepSpec(
                    id="edges",
                    operation="canny",
                    inputs={"image": step_output("blur")},
                    params={"threshold_low": 50, "threshold_high": 150},
                ),
                PipelineStepSpec(
                    id="lines",
                    operation="hough_lines_p",
                    inputs={"image": step_output("edges")},
                    params={"threshold": 30, "min_line_length": 20.0, "max_line_gap": 8.0},
                ),
            ],
            outputs={
                "image": step_output("lines", "image"),
                "lines": step_output("lines", "lines"),
                "edges": step_output("edges"),
            },
        ),
        PipelineSpec(
            name="circle_detection",
            display_name="Circle Detection",
            description="중앙값 필터 후 Hough circle을 검출합니다.",
            inputs=[image_input()],
            steps=[
                _gray_step(pipeline_input("image")),
                PipelineStepSpec(
                    id="denoise",
                    operation="median_blur",
                    inputs={"image": step_output("gray")},
                    params={"kernel_size": 5},
                ),
                PipelineStepSpec(
                    id="circles",
                    operation="hough_circles",
                    inputs={"image": step_output("denoise")},
                    params={
                        "dp": 1.2,
                        "min_distance": 20.0,
                        "canny_threshold": 100.0,
                        "accumulator_threshold": 25.0,
                    },
                ),
            ],
            outputs={
                "image": step_output("circles", "image"),
                "circles": step_output("circles", "circles"),
            },
        ),
        PipelineSpec(
            name="color_segmentation",
            display_name="Color Segmentation",
            description="경계 보존 평활화 후 K-Means로 색상 영역을 분할합니다.",
            inputs=[photo_input()],
            steps=[
                PipelineStepSpec(
                    id="smooth",
                    operation="edge_preserving_filter",
                    inputs={"image": pipeline_input("image")},
                    params={"method": "recursive", "sigma_s": 40.0, "sigma_r": 0.3},
                ),
                PipelineStepSpec(
                    id="segment",
                    operation="kmeans_segmentation",
                    inputs={"image": step_output("smooth")},
                    params={"clusters": 5, "sample_size": 100_000, "attempts": 3},
                ),
            ],
            outputs={
                "image": step_output("segment", "image"),
                "labels": step_output("segment", "labels"),
                "centers": step_output("segment", "centers"),
                "compactness": step_output("segment", "compactness"),
            },
        ),
    ]
