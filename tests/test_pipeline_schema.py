import pytest
from pydantic import ValidationError

from src.pipeline import pipeline_input, step_output
from src.schemas import (
    InputKind,
    InputSlotSpec,
    PipelineSpec,
    PipelineStepSpec,
)


def test_pipeline_rejects_forward_step_reference():
    with pytest.raises(ValidationError):
        PipelineSpec(
            name="invalid_pipeline",
            display_name="Invalid Pipeline",
            inputs=[
                InputSlotSpec(name="image", kind=InputKind.IMAGE)
            ],
            steps=[
                PipelineStepSpec(
                    id="first",
                    operation="gaussian_blur",
                    inputs={
                        "image": step_output("second")
                    },
                ),
                PipelineStepSpec(
                    id="second",
                    operation="resize",
                    inputs={
                        "image": pipeline_input("image")
                    },
                    params={"width": 4, "height": 4},
                ),
            ],
        )


def test_pipeline_rejects_duplicate_step_ids():
    with pytest.raises(ValidationError):
        PipelineSpec(
            name="invalid_pipeline",
            display_name="Invalid Pipeline",
            inputs=[
                InputSlotSpec(name="image", kind=InputKind.IMAGE)
            ],
            steps=[
                PipelineStepSpec(
                    id="duplicate",
                    operation="gaussian_blur",
                    inputs={
                        "image": pipeline_input("image")
                    },
                ),
                PipelineStepSpec(
                    id="duplicate",
                    operation="resize",
                    inputs={
                        "image": pipeline_input("image")
                    },
                    params={"width": 4, "height": 4},
                ),
            ],
        )


def test_pipeline_rejects_unknown_pipeline_input_reference():
    with pytest.raises(ValidationError):
        PipelineSpec(
            name="invalid_pipeline",
            display_name="Invalid Pipeline",
            inputs=[
                InputSlotSpec(name="image", kind=InputKind.IMAGE)
            ],
            steps=[
                PipelineStepSpec(
                    id="blur",
                    operation="gaussian_blur",
                    inputs={
                        "image": pipeline_input("unknown")
                    },
                )
            ],
        )


def test_pipeline_spec_json_round_trip():
    pipeline = PipelineSpec(
        name="json_pipeline",
        display_name="JSON Pipeline",
        inputs=[
            InputSlotSpec(name="image", kind=InputKind.IMAGE)
        ],
        steps=[
            PipelineStepSpec(
                id="blur",
                operation="gaussian_blur",
                inputs={"image": pipeline_input("image")},
                params={"kernel_size": 5},
            )
        ],
        outputs={"image": step_output("blur")},
    )

    restored = PipelineSpec.model_validate_json(
        pipeline.model_dump_json()
    )

    assert restored == pipeline
