import numpy as np

from src.registry import create_default_registry
from src.schemas import ColorSpace, ImageData


registry = create_default_registry()

image = ImageData(
    data=np.zeros((480, 640), dtype=np.uint8),
    color_space=ColorSpace.GRAY,
    name="sample",
)

result = registry.execute(
    operation="gaussian_blur",
    inputs={"image": image},
    params={
        "kernel_size": 7,
        "sigma_x": 1.5,
        "border_type": "reflect",
    },
)

if result.success:
    output_image = result.output.images["image"]
    print(output_image.shape)
else:
    assert result.error is not None
    print(result.error.model_dump(mode="json"))
