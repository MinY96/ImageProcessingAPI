from __future__ import annotations

from collections.abc import Mapping
from threading import RLock
from typing import Any

import numpy as np

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
    ImageData,
    InputKind,
    InputSlotSpec,
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)

from ..common import as_image, ensure_pixel_budget, to_bgr


_KMEANS_RNG_LOCK = RLock()


def sampled_kmeans(
    samples: np.ndarray,
    *,
    clusters: int,
    sample_size: int,
    max_iterations: int,
    epsilon: float,
    attempts: int,
    initialization: str,
    random_seed: int,
    chunk_size: int = 250_000,
) -> tuple[np.ndarray, np.ndarray, float]:
    """표본으로 center를 학습하고 전체 sample을 chunk 단위로 배정한다."""
    import cv2

    values = np.asarray(samples, dtype=np.float32)
    if values.ndim != 2 or values.shape[0] < clusters:
        raise ValueError("samples must have shape (N, D) with N >= clusters")
    count = values.shape[0]
    rng = np.random.default_rng(random_seed)
    if count > sample_size:
        selected = rng.choice(count, size=sample_size, replace=False)
        training = np.ascontiguousarray(values[selected])
    else:
        training = np.ascontiguousarray(values)

    flags = {
        "kmeans_pp": cv2.KMEANS_PP_CENTERS,
        "random": cv2.KMEANS_RANDOM_CENTERS,
    }[initialization]
    criteria = (
        cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER,
        max_iterations,
        epsilon,
    )
    with _KMEANS_RNG_LOCK:
        cv2.setRNGSeed(int(random_seed))
        _, _, centers = cv2.kmeans(
            training, clusters, None, criteria, attempts, flags
        )

    labels = np.empty(count, dtype=np.int32)
    compactness = 0.0
    for start in range(0, count, chunk_size):
        stop = min(count, start + chunk_size)
        chunk = values[start:stop]
        distances = np.sum(
            (chunk[:, None, :] - centers[None, :, :]) ** 2,
            axis=2,
        )
        chunk_labels = np.argmin(distances, axis=1).astype(np.int32)
        labels[start:stop] = chunk_labels
        compactness += float(
            distances[np.arange(stop - start), chunk_labels].sum(dtype=np.float64)
        )
    return labels, centers.astype(np.float32), compactness


KMEANS_SEGMENTATION_SPEC = OperationSpec(
    name="kmeans_segmentation",
    display_name="K-Means Segmentation",
    category=OperationCategory.SEGMENTATION,
    inputs=[InputSlotSpec(name="image", kind=InputKind.IMAGE)],
    parameters={
        "clusters": DiscreteParameterSpec(
            title="Clusters", min_value=2, max_value=32, default=5
        ),
        "sample_size": DiscreteParameterSpec(
            title="Training Sample Pixels",
            min_value=1000,
            max_value=1_000_000,
            default=100_000,
        ),
        "max_iterations": DiscreteParameterSpec(
            title="Maximum Iterations", min_value=1, max_value=1000, default=30
        ),
        "epsilon": ContinuousParameterSpec(
            title="Epsilon", min_value=0.0001, max_value=100.0, default=0.5
        ),
        "attempts": DiscreteParameterSpec(
            title="Attempts", min_value=1, max_value=20, default=3
        ),
        "initialization": CategoryParameterSpec(
            title="Initialization",
            choices=[
                CategoryChoice(value="kmeans_pp", label="K-Means++"),
                CategoryChoice(value="random", label="Random"),
            ],
            default="kmeans_pp",
        ),
        "random_seed": DiscreteParameterSpec(
            title="Random Seed", min_value=0, max_value=2_147_483_647, default=42
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="labels", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="centers", kind=OutputKind.ARRAY),
        OutputSlotSpec(name="compactness", kind=OutputKind.SCALAR),
    ],
)


def _pixels(image: ImageData) -> tuple[np.ndarray, tuple[int, int], ColorSpace]:
    if image.color_space in {ColorSpace.GRAY, ColorSpace.BINARY}:
        array = image.data
        samples = array.reshape(-1, 1)
        output_space = ColorSpace.GRAY
    else:
        array = to_bgr(image)
        samples = array.reshape(-1, 3)
        output_space = ColorSpace.BGR
    return np.asarray(samples, dtype=np.float32), array.shape[:2], output_space


def kmeans_segmentation_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="kmeans_segmentation",
        max_pixels=16_000_000,
    )
    samples, shape, output_space = _pixels(image)
    labels, centers, compactness = sampled_kmeans(
        samples,
        clusters=params["clusters"],
        sample_size=params["sample_size"],
        max_iterations=params["max_iterations"],
        epsilon=params["epsilon"],
        attempts=params["attempts"],
        initialization=params["initialization"],
        random_seed=params["random_seed"],
    )
    quantized = centers[labels]
    if output_space == ColorSpace.GRAY:
        quantized = quantized.reshape(shape)
    else:
        quantized = quantized.reshape((*shape, 3))
    if np.issubdtype(image.data.dtype, np.integer):
        info = np.iinfo(image.data.dtype)
        quantized = np.clip(np.rint(quantized), info.min, info.max).astype(image.data.dtype)
    else:
        quantized = quantized.astype(image.data.dtype)
    label_image = labels.reshape(shape).astype(np.int32)
    return OperationOutput(
        images={
            "image": as_image(
                quantized,
                source=image,
                color_space=output_space,
                name="kmeans_segmented",
            ),
            "labels": as_image(
                label_image,
                source=image,
                color_space=ColorSpace.UNKNOWN,
                name="kmeans_labels",
            ),
        },
        data={"centers": centers, "compactness": compactness},
    )
