import numpy as np

from src.pipeline import PipelineExecutor, pipeline_input, step_output
from src.registry import create_default_registry
from src.schemas import (
    ColorSpace,
    ImageData,
    InputKind,
    InputSlotSpec,
    PipelineSpec,
    PipelineStepSpec,
)


def main() -> None:
    height, width = 240, 320
    y, x = np.mgrid[:height, :width]
    image = ImageData(
        data=np.stack(
            [
                x * 255 // (width - 1),
                y * 255 // (height - 1),
                (x + y) * 255 // (width + height - 2),
            ],
            axis=2,
        ).astype(np.uint8),
        color_space=ColorSpace.BGR,
        name="gradient",
    )
    pipeline = PipelineSpec(
        name="film_look",
        display_name="Film Look",
        inputs=[InputSlotSpec(name="image", kind=InputKind.IMAGE)],
        steps=[
            PipelineStepSpec(
                id="tone",
                operation="adjust_tone",
                inputs={"image": pipeline_input("image")},
                params={"contrast": 0.9, "brightness": 0.04},
            ),
            PipelineStepSpec(
                id="vignette",
                operation="vignette",
                inputs={"image": step_output("tone")},
                params={"strength": 0.35},
            ),
            PipelineStepSpec(
                id="grain",
                operation="add_grain",
                inputs={"image": step_output("vignette")},
                params={"amount": 0.03, "random_seed": 11},
            ),
        ],
        outputs={"image": step_output("grain")},
    )
    result = PipelineExecutor(create_default_registry()).execute(
        pipeline=pipeline,
        inputs={"image": image},
    )
    if not result.success:
        raise RuntimeError(result.error)
    output = result.output.images["image"]
    print(output.shape, output.color_space, output.dtype)


if __name__ == "__main__":
    main()
