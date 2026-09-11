from __future__ import annotations

from src.workflow.schemas import (
    DecisionNodeSpec,
    FeatureNodeSpec,
    GraphInputReference,
    GraphRecipeSpec,
    NodeOutputReference,
    OperationNodeSpec,
    RoiComposeNodeSpec,
    RoiCropNodeSpec,
    ScalarOperatorNodeSpec,
    SubRecipeNodeSpec,
    WorkflowDataKind,
    WorkflowPortSpec,
)


def graph_input(name: str) -> GraphInputReference:
    return GraphInputReference(input_name=name)


def node_output(node_id: str, output_name: str = "image") -> NodeOutputReference:
    return NodeOutputReference(node_id=node_id, output_name=output_name)


def create_builtin_graph_recipes() -> list[GraphRecipeSpec]:
    return [
        _branched_binary_feature_score(),
        _multi_roi_feature_fusion(),
        _multi_roi_image_recompose(),
        _nested_linear_recipe_score(),
        _nested_graph_recipe_score(),
    ]


def _image_input() -> list[WorkflowPortSpec]:
    return [WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE)]


def _branched_binary_feature_score() -> GraphRecipeSpec:
    """Binary 결과 하나를 3개 branch가 공유하고 feature score를 다시 합친다."""
    return GraphRecipeSpec(
        name="rule_branch_binary_score",
        display_name="Rule - Branched Binary Feature Score",
        description=(
            "Gray/Otsu binary 이후 동일 mask를 open/gradient/close 세 branch로 분기하고 "
            "각 branch의 면적 계열 feature를 weighted score로 합쳐 판정합니다."
        ),
        inputs=_image_input(),
        nodes=[
            OperationNodeSpec(
                id="gray", operation="convert_color",
                inputs={"image": graph_input("image")},
                params={"target_color_space": "gray"},
            ),
            OperationNodeSpec(
                id="binary", operation="global_threshold",
                inputs={"image": node_output("gray")},
                params={"use_otsu": True, "mode": "binary"},
            ),
            OperationNodeSpec(
                id="open_branch", operation="morphology",
                inputs={"image": node_output("binary")},
                params={"operation": "open", "kernel_shape": "ellipse", "kernel_size": 3},
            ),
            FeatureNodeSpec(
                id="open_ratio", feature="pixel_statistic",
                inputs={"image": node_output("open_branch")},
                params={"statistic": "nonzero_ratio"},
            ),
            OperationNodeSpec(
                id="gradient_branch", operation="morphology",
                inputs={"image": node_output("binary")},
                params={"operation": "gradient", "kernel_shape": "rect", "kernel_size": 3},
            ),
            FeatureNodeSpec(
                id="gradient_ratio", feature="pixel_statistic",
                inputs={"image": node_output("gradient_branch")},
                params={"statistic": "nonzero_ratio"},
            ),
            OperationNodeSpec(
                id="close_branch", operation="morphology",
                inputs={"image": node_output("binary")},
                params={"operation": "close", "kernel_shape": "rect", "kernel_size": 5},
            ),
            FeatureNodeSpec(
                id="largest_region", feature="contour_feature",
                inputs={"image": node_output("close_branch")},
                params={"feature": "largest_area_ratio", "min_area": 4.0},
            ),
            ScalarOperatorNodeSpec(
                id="score", operator="weighted_sum",
                inputs={
                    "foreground": node_output("open_ratio", "value"),
                    "boundary": node_output("gradient_ratio", "value"),
                    "largest": node_output("largest_region", "value"),
                },
                params={"weights": {"foreground": 0.45, "boundary": 0.25, "largest": 0.30}},
            ),
            DecisionNodeSpec(
                id="decision",
                inputs={"value": node_output("score", "value")},
                params={"operator": "lte", "threshold": 0.25, "pass_label": "OK", "fail_label": "NG"},
            ),
        ],
        outputs={
            "binary": node_output("binary"),
            "foreground_ratio": node_output("open_ratio", "value"),
            "boundary_ratio": node_output("gradient_ratio", "value"),
            "largest_area_ratio": node_output("largest_region", "value"),
            "score": node_output("score", "value"),
            "passed": node_output("decision", "passed"),
            "result": node_output("decision", "label"),
        },
    )


def _multi_roi_feature_fusion() -> GraphRecipeSpec:
    """3개 ROI를 서로 다른 전처리로 처리하고 feature를 하나의 score로 합친다."""
    return GraphRecipeSpec(
        name="rule_multi_roi_fusion",
        display_name="Rule - Multi ROI Feature Fusion",
        description=(
            "이미지를 좌/중/우 ROI로 나누어 Gaussian, CLAHE, Canny의 서로 다른 branch를 적용한 뒤 "
            "정규화 feature를 weighted mean으로 합칩니다."
        ),
        inputs=_image_input(),
        nodes=[
            RoiCropNodeSpec(
                id="left_roi", inputs={"image": graph_input("image")},
                params={"coordinate_mode": "relative", "x": 0.0, "y": 0.0, "width": 0.333, "height": 1.0},
            ),
            OperationNodeSpec(
                id="left_gray", operation="convert_color", inputs={"image": node_output("left_roi")},
                params={"target_color_space": "gray"},
            ),
            OperationNodeSpec(
                id="left_blur", operation="gaussian_blur", inputs={"image": node_output("left_gray")},
                params={"kernel_size": 5},
            ),
            FeatureNodeSpec(
                id="left_mean", feature="pixel_statistic", inputs={"image": node_output("left_blur")},
                params={"statistic": "mean"},
            ),
            ScalarOperatorNodeSpec(
                id="left_norm", operator="normalize_range", inputs={"value": node_output("left_mean", "value")},
                params={"lower": 0.0, "upper": 255.0, "clip": True},
            ),
            RoiCropNodeSpec(
                id="center_roi", inputs={"image": graph_input("image")},
                params={"coordinate_mode": "relative", "x": 0.333, "y": 0.0, "width": 0.334, "height": 1.0},
            ),
            OperationNodeSpec(
                id="center_gray", operation="convert_color", inputs={"image": node_output("center_roi")},
                params={"target_color_space": "gray"},
            ),
            OperationNodeSpec(
                id="center_clahe", operation="clahe", inputs={"image": node_output("center_gray")},
                params={"clip_limit": 2.5, "tile_grid_size": 8},
            ),
            FeatureNodeSpec(
                id="center_mean", feature="pixel_statistic", inputs={"image": node_output("center_clahe")},
                params={"statistic": "mean"},
            ),
            ScalarOperatorNodeSpec(
                id="center_norm", operator="normalize_range", inputs={"value": node_output("center_mean", "value")},
                params={"lower": 0.0, "upper": 255.0, "clip": True},
            ),
            RoiCropNodeSpec(
                id="right_roi", inputs={"image": graph_input("image")},
                params={"coordinate_mode": "relative", "x": 0.667, "y": 0.0, "width": 0.333, "height": 1.0},
            ),
            OperationNodeSpec(
                id="right_gray", operation="convert_color", inputs={"image": node_output("right_roi")},
                params={"target_color_space": "gray"},
            ),
            OperationNodeSpec(
                id="right_edges", operation="canny", inputs={"image": node_output("right_gray")},
                params={"threshold_low": 60, "threshold_high": 160},
            ),
            FeatureNodeSpec(
                id="right_edge_ratio", feature="pixel_statistic", inputs={"image": node_output("right_edges")},
                params={"statistic": "nonzero_ratio"},
            ),
            ScalarOperatorNodeSpec(
                id="fusion", operator="weighted_mean",
                inputs={
                    "left": node_output("left_norm", "value"),
                    "center": node_output("center_norm", "value"),
                    "right": node_output("right_edge_ratio", "value"),
                },
                params={"weights": {"left": 0.3, "center": 0.3, "right": 0.4}},
            ),
            DecisionNodeSpec(
                id="decision", inputs={"value": node_output("fusion", "value")},
                params={"operator": "lte", "threshold": 0.55},
            ),
        ],
        outputs={
            "left_processed": node_output("left_blur"),
            "center_processed": node_output("center_clahe"),
            "right_processed": node_output("right_edges"),
            "score": node_output("fusion", "value"),
            "passed": node_output("decision", "passed"),
            "result": node_output("decision", "label"),
        },
    )


def _multi_roi_image_recompose() -> GraphRecipeSpec:
    """ROI별로 다른 전처리를 거친 뒤 원래 좌표에 다시 합성한다."""
    return GraphRecipeSpec(
        name="rule_multi_roi_recompose",
        display_name="Rule - Multi ROI Image Recompose",
        description=(
            "Gray 이미지의 좌/중/우 ROI를 각각 Gaussian/CLAHE/Median으로 처리하고 ROI metadata를 이용해 "
            "원래 좌표에 다시 합성합니다."
        ),
        inputs=_image_input(),
        nodes=[
            OperationNodeSpec(
                id="gray", operation="convert_color", inputs={"image": graph_input("image")},
                params={"target_color_space": "gray"},
            ),
            RoiCropNodeSpec(
                id="left_roi", inputs={"image": node_output("gray")},
                params={"coordinate_mode": "relative", "x": 0.0, "y": 0.0, "width": 0.333, "height": 1.0},
            ),
            OperationNodeSpec(
                id="left_process", operation="gaussian_blur", inputs={"image": node_output("left_roi")},
                params={"kernel_size": 7},
            ),
            RoiCropNodeSpec(
                id="center_roi", inputs={"image": node_output("gray")},
                params={"coordinate_mode": "relative", "x": 0.333, "y": 0.0, "width": 0.334, "height": 1.0},
            ),
            OperationNodeSpec(
                id="center_process", operation="clahe", inputs={"image": node_output("center_roi")},
                params={"clip_limit": 2.0, "tile_grid_size": 8},
            ),
            RoiCropNodeSpec(
                id="right_roi", inputs={"image": node_output("gray")},
                params={"coordinate_mode": "relative", "x": 0.667, "y": 0.0, "width": 0.333, "height": 1.0},
            ),
            OperationNodeSpec(
                id="right_process", operation="median_blur", inputs={"image": node_output("right_roi")},
                params={"kernel_size": 5},
            ),
            RoiComposeNodeSpec(
                id="compose_left",
                inputs={
                    "base": node_output("gray"), "patch": node_output("left_process"),
                    "region": node_output("left_roi", "region"),
                },
            ),
            RoiComposeNodeSpec(
                id="compose_center",
                inputs={
                    "base": node_output("compose_left"), "patch": node_output("center_process"),
                    "region": node_output("center_roi", "region"),
                },
            ),
            RoiComposeNodeSpec(
                id="compose_right",
                inputs={
                    "base": node_output("compose_center"), "patch": node_output("right_process"),
                    "region": node_output("right_roi", "region"),
                },
            ),
        ],
        outputs={"image": node_output("compose_right")},
    )


def _nested_linear_recipe_score() -> GraphRecipeSpec:
    """기존 20개 linear recipe 중 하나를 graph node 안에 넣는다."""
    return GraphRecipeSpec(
        name="rule_nested_sem_profile",
        display_name="Rule - Nested SEM Profile Recipe",
        description=(
            "기존 linear recipe인 sem_profile_edges를 SubRecipe node로 재사용하고 profile mask 비율로 판정합니다."
        ),
        inputs=_image_input(),
        nodes=[
            SubRecipeNodeSpec(
                id="sem_profile", recipe="sem_profile_edges", recipe_kind="linear",
                recipe_version="1.0.0", inputs={"image": graph_input("image")},
            ),
            FeatureNodeSpec(
                id="profile_ratio", feature="pixel_statistic",
                inputs={"image": node_output("sem_profile", "profile_mask")},
                params={"statistic": "nonzero_ratio"},
            ),
            DecisionNodeSpec(
                id="decision", inputs={"value": node_output("profile_ratio", "value")},
                params={"operator": "lte", "threshold": 0.35},
            ),
        ],
        outputs={
            "profile_mask": node_output("sem_profile", "profile_mask"),
            "gradient": node_output("sem_profile", "gradient"),
            "score": node_output("profile_ratio", "value"),
            "passed": node_output("decision", "passed"),
            "result": node_output("decision", "label"),
        },
    )


def _nested_graph_recipe_score() -> GraphRecipeSpec:
    """Graph recipe 자체를 다른 graph recipe의 하나의 node로 재사용한다."""
    return GraphRecipeSpec(
        name="rule_nested_graph_score",
        display_name="Rule - Nested Graph Recipe Score",
        description=(
            "rule_branch_binary_score 전체를 SubRecipe node 하나로 넣고 상위 recipe에서 별도의 판정 기준을 적용합니다."
        ),
        inputs=_image_input(),
        nodes=[
            SubRecipeNodeSpec(
                id="base_rule", recipe="rule_branch_binary_score", recipe_kind="graph",
                recipe_version="1.0.0", inputs={"image": graph_input("image")},
            ),
            DecisionNodeSpec(
                id="strict_decision", inputs={"value": node_output("base_rule", "score")},
                params={"operator": "lte", "threshold": 0.20, "pass_label": "OK", "fail_label": "NG"},
            ),
        ],
        outputs={
            "binary": node_output("base_rule", "binary"),
            "score": node_output("base_rule", "score"),
            "passed": node_output("strict_decision", "passed"),
            "result": node_output("strict_decision", "label"),
        },
    )
