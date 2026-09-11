import numpy as np

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


pipeline = PipelineSpec(
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
            params={
                "threshold_low": 50,
                "threshold_high": 150,
            },
        ),
    ],
    outputs={"edges": step_output("edges")},
)

image = ImageData(
    data=np.zeros((480, 640), dtype=np.uint8),
    color_space=ColorSpace.GRAY,
)

executor = PipelineExecutor(create_default_registry())
compiled = executor.compile(pipeline)
result = executor.execute(
    pipeline=compiled,
    inputs={"image": image},
)

if result.success:
    print(result.output.images["edges"].shape)
    print([step.step_id for step in result.steps])
else:
    print(result.error)
