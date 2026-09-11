import cv2
import numpy as np

from src.machine_learning import ModelRegistry, train_knn
from src.registry import create_default_registry
from src.schemas import ColorSpace, ImageData


registry = create_default_registry()

rng = np.random.default_rng(7)
pixels = rng.integers(0, 80, (192, 256), dtype=np.uint8)
cv2.rectangle(pixels, (20, 20), (110, 150), 230, 4)
cv2.circle(pixels, (180, 90), 42, 255, 4)
image = ImageData(data=pixels, color_space=ColorSpace.GRAY, name="demo")

features = registry.execute(
    operation="orb_features",
    inputs={"image": image},
)
assert features.success, features.error
print("ORB keypoints:", len(features.output.data["keypoints"]))
print("ORB descriptors:", features.output.data["descriptors"].shape)

segmented = registry.execute(
    operation="kmeans_segmentation",
    inputs={"image": image},
    params={"clusters": 3, "random_seed": 42},
)
assert segmented.success, segmented.error
print("K-Means centers:", segmented.output.data["centers"].reshape(-1))

model = train_knn(
    [[0.0, 0.0], [0.0, 1.0], [8.0, 8.0], [9.0, 8.0]],
    [0, 0, 1, 1],
    model_id="demo_knn",
    version="1.0.0",
    feature_schema="xy-v1",
    default_k=1,
    label_names={0: "low", 1: "high"},
)
models = ModelRegistry()
models.register(model)

prediction = registry.execute(
    operation="model_predict",
    inputs={
        "model": models.get("demo_knn", "1.0.0"),
        "features": [[0.2, 0.1], [8.4, 8.2]],
    },
    params={"knn_k": 1},
)
assert prediction.success, prediction.error
print("Predictions:", prediction.output.data["prediction_info"].label_names)
