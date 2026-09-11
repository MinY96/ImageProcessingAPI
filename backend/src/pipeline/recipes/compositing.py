from src.pipeline.references import pipeline_input, step_output
from src.schemas import ColorSpace, PipelineSpec, PipelineStepSpec

from .common import image_input, mask_input, photo_input


def create_compositing_recipes() -> list[PipelineSpec]:
    return [
        PipelineSpec(
            name="masked_local_enhancement",
            display_name="Masked Local Enhancement",
            description="마스크 영역에만 detail과 tone 보정 결과를 합성합니다.",
            inputs=[
                image_input("image", color_spaces=[ColorSpace.BGR]),
                mask_input(),
            ],
            steps=[
                PipelineStepSpec(
                    id="detail",
                    operation="detail_enhance",
                    inputs={"image": pipeline_input("image")},
                    params={"sigma_s": 10.0, "sigma_r": 0.15},
                ),
                PipelineStepSpec(
                    id="tone",
                    operation="adjust_tone",
                    inputs={"image": step_output("detail")},
                    params={"exposure": 0.15, "contrast": 1.12},
                ),
                PipelineStepSpec(
                    id="blend",
                    operation="apply_mask",
                    inputs={
                        "base": pipeline_input("image"),
                        "effect": step_output("tone"),
                        "mask": pipeline_input("mask"),
                    },
                    params={"opacity": 1.0},
                ),
            ],
            outputs={"image": step_output("blend")},
        ),
        PipelineSpec(
            name="seamless_composite",
            display_name="Seamless Composite",
            description="Source를 mask와 destination 중심 좌표에 자연스럽게 합성합니다.",
            inputs=[photo_input("source"), photo_input("destination"), mask_input()],
            steps=[
                PipelineStepSpec(
                    id="clone",
                    operation="seamless_clone",
                    inputs={
                        "source": pipeline_input("source"),
                        "destination": pipeline_input("destination"),
                        "mask": pipeline_input("mask"),
                    },
                    params={"center_x": 320, "center_y": 240, "mode": "mixed"},
                )
            ],
            outputs={"image": step_output("clone")},
        ),
    ]
