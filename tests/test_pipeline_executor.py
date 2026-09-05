import numpy as np
import pytest

pytest.importorskip("cv2")

from src.pipeline import (
    PipelineExecutor,
    pipeline_input,
    step_output,
)
from src.registry import create_default_registry
from src.schemas import (
    ColorSpace,
    ImageData,
    InputKind,
    InputSlotSpec,
    PipelineSpec,
    PipelineStepSpec,
)


def make_image() -> ImageData:
    data = np.zeros((16, 20), dtype=np.uint8)
    data[4:12, 6:14] = 255
    return ImageData(
        data=data,
        color_space=ColorSpace.GRAY,
        name="sample",
    )


def make_success_pipeline(
    *,
    explicit_output: bool = True,
) -> PipelineSpec:
    return PipelineSpec(
        name="edge_thumbnail",
        display_name="Edge Thumbnail",
        inputs=[
            InputSlotSpec(name="image", kind=InputKind.IMAGE)
        ],
        steps=[
            PipelineStepSpec(
                id="blur",
                operation="gaussian_blur",
                inputs={"image": pipeline_input("image")},
                params={"kernel_size": 3},
            ),
            PipelineStepSpec(
                id="resize",
                operation="resize",
                inputs={"image": step_output("blur")},
                params={"width": 10, "height": 8},
            ),
            PipelineStepSpec(
                id="edges",
                operation="canny",
                inputs={"image": step_output("resize")},
                params={
                    "threshold_low": 50,
                    "threshold_high": 150,
                },
            ),
        ],
        outputs=(
            {"edges": step_output("edges")}
            if explicit_output
            else {}
        ),
    )


def test_pipeline_executes_operations_in_order():
    executor = PipelineExecutor(create_default_registry())

    result = executor.execute(
        pipeline=make_success_pipeline(),
        inputs={"image": make_image()},
    )

    assert result.success is True
    assert [step.step_id for step in result.steps] == [
        "blur",
        "resize",
        "edges",
    ]
    assert result.output.images["edges"].shape == (8, 10)
    assert result.output.images["edges"].color_space == (
        ColorSpace.BINARY
    )
    assert result.intermediates == {}


def test_compiled_pipeline_can_be_reused():
    executor = PipelineExecutor(create_default_registry())
    compiled = executor.compile(make_success_pipeline())

    first = executor.execute(
        pipeline=compiled,
        inputs={"image": make_image()},
    )
    second = executor.execute(
        pipeline=compiled,
        inputs={"image": make_image()},
    )

    assert first.success is True
    assert second.success is True


def test_compiled_pipeline_recompiles_after_registry_change():
    registry = create_default_registry()
    executor = PipelineExecutor(registry)
    compiled = executor.compile(make_success_pipeline())
    initial_revision = compiled.registry_revision

    gaussian_spec = registry.get_spec("gaussian_blur")
    from src.image_processing import gaussian_blur_handler

    registry.register(
        spec=gaussian_spec,
        handler=gaussian_blur_handler,
        replace=True,
    )

    result = executor.execute(
        pipeline=compiled,
        inputs={"image": make_image()},
    )

    assert registry.revision > initial_revision
    assert result.success is True


def test_final_step_outputs_are_used_by_default():
    executor = PipelineExecutor(create_default_registry())
    result = executor.execute(
        pipeline=make_success_pipeline(explicit_output=False),
        inputs={"image": make_image()},
    )

    assert result.success is True
    assert set(result.output.images) == {"image"}


def test_intermediates_are_retained_only_when_requested():
    executor = PipelineExecutor(create_default_registry())
    result = executor.execute(
        pipeline=make_success_pipeline(),
        inputs={"image": make_image()},
        retain_intermediates=True,
    )

    assert result.success is True
    assert set(result.intermediates) == {
        "blur",
        "resize",
        "edges",
    }


def test_one_step_output_can_feed_multiple_later_steps():
    pipeline = PipelineSpec(
        name="branched_linear_pipeline",
        display_name="Branched Linear Pipeline",
        inputs=[
            InputSlotSpec(name="image", kind=InputKind.IMAGE)
        ],
        steps=[
            PipelineStepSpec(
                id="blur",
                operation="gaussian_blur",
                inputs={"image": pipeline_input("image")},
                params={"kernel_size": 3},
            ),
            PipelineStepSpec(
                id="small",
                operation="resize",
                inputs={"image": step_output("blur")},
                params={"width": 10, "height": 8},
            ),
            PipelineStepSpec(
                id="edges",
                operation="canny",
                inputs={"image": step_output("blur")},
            ),
        ],
        outputs={
            "small": step_output("small"),
            "edges": step_output("edges"),
        },
    )

    result = PipelineExecutor(
        create_default_registry()
    ).execute(
        pipeline=pipeline,
        inputs={"image": make_image()},
    )

    assert result.success is True
    assert result.output.images["small"].shape == (8, 10)
    assert result.output.images["edges"].shape == (16, 20)


def test_missing_pipeline_input_returns_failure():
    executor = PipelineExecutor(create_default_registry())
    result = executor.execute(
        pipeline=make_success_pipeline(),
        inputs={},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "pipeline_input_validation_error"
    assert result.steps == []


def test_invalid_later_step_is_detected_before_execution():
    pipeline = make_success_pipeline()
    pipeline.steps[1].params = {"width": 10}

    executor = PipelineExecutor(create_default_registry())
    result = executor.execute(
        pipeline=pipeline,
        inputs={"image": make_image()},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "pipeline_validation_error"
    assert result.steps == []
    assert any(
        issue["code"] == "partial_group"
        for issue in result.error.details["issues"]
    )


def test_unknown_operation_is_preflight_failure():
    pipeline = make_success_pipeline()
    pipeline.steps[1].operation = "not_registered"

    result = PipelineExecutor(
        create_default_registry()
    ).execute(
        pipeline=pipeline,
        inputs={"image": make_image()},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "pipeline_validation_error"
    assert result.steps == []


def test_incompatible_binding_kind_is_preflight_failure():
    pipeline = PipelineSpec(
        name="invalid_kind",
        display_name="Invalid Kind",
        inputs=[
            InputSlotSpec(
                name="contours",
                kind=InputKind.CONTOURS,
            )
        ],
        steps=[
            PipelineStepSpec(
                id="blur",
                operation="gaussian_blur",
                inputs={
                    "image": pipeline_input("contours")
                },
            )
        ],
    )

    result = PipelineExecutor(
        create_default_registry()
    ).execute(
        pipeline=pipeline,
        inputs={"contours": []},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "pipeline_validation_error"
    assert result.error.details["issues"][0]["code"] == (
        "incompatible_input_kind"
    )


def test_runtime_step_failure_stops_pipeline():
    pipeline = make_success_pipeline()
    pipeline.steps[1].params = {
        "scale_x": 10.0,
        "scale_y": 10.0,
    }
    large_image = ImageData(
        data=np.zeros((1000, 1000), dtype=np.uint8),
        color_space=ColorSpace.GRAY,
    )

    result = PipelineExecutor(
        create_default_registry()
    ).execute(
        pipeline=pipeline,
        inputs={"image": large_image},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "pipeline_step_failed"
    assert result.error.step_id == "resize"
    assert result.error.details["cause"]["code"] == (
        "resource_limit_exceeded"
    )
    assert [step.step_id for step in result.steps] == [
        "blur",
        "resize",
    ]
