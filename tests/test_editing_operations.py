import cv2
import numpy as np
import pytest

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


@pytest.fixture
def registry():
    return create_default_registry()


@pytest.fixture
def bgr_image():
    y, x = np.mgrid[:72, :96]
    data = np.stack(
        [
            (x * 255 // 95),
            (y * 255 // 71),
            ((x + y) * 255 // 166),
        ],
        axis=2,
    ).astype(np.uint8)
    return ImageData(data=data, color_space=ColorSpace.BGR, name="gradient")


def assert_success(result):
    assert result.success is True, result.error
    return result.output.images


def test_tone_color_invert_and_alpha_preservation(registry, bgr_image):
    tone = registry.execute(
        operation="adjust_tone",
        inputs={"image": bgr_image},
        params={"exposure": 0.5, "contrast": 1.1, "gamma": 0.9},
    )
    assert_success(tone)
    assert tone.output.images["image"].shape == bgr_image.shape

    color = registry.execute(
        operation="adjust_color",
        inputs={"image": bgr_image},
        params={"hue_shift": 30, "vibrance": 0.4, "temperature": 0.2},
    )
    assert_success(color)
    assert not np.array_equal(color.output.images["image"].data, bgr_image.data)

    alpha = np.full(bgr_image.shape[:2], 73, dtype=np.uint8)
    bgra = ImageData(
        data=np.dstack([bgr_image.data, alpha]),
        color_space=ColorSpace.BGRA,
    )
    inverted = registry.execute(operation="invert", inputs={"image": bgra})
    assert_success(inverted)
    assert np.array_equal(inverted.output.images["image"].data[..., 3], alpha)
    assert np.array_equal(
        inverted.output.images["image"].data[..., :3],
        np.bitwise_not(bgra.data[..., :3]),
    )


def test_one_dimensional_and_three_dimensional_luts(registry, bgr_image):
    negative_lut = np.arange(255, -1, -1, dtype=np.uint8)
    one_d = registry.execute(
        operation="apply_lut",
        inputs={"image": bgr_image, "lut": negative_lut},
    )
    assert_success(one_d)
    assert np.array_equal(one_d.output.images["image"].data, 255 - bgr_image.data)

    axis = np.linspace(0.0, 1.0, 4, dtype=np.float32)
    red, green, blue = np.meshgrid(axis, axis, axis, indexing="ij")
    identity_cube = np.stack([red, green, blue], axis=-1)
    three_d = registry.execute(
        operation="apply_3d_lut",
        inputs={"image": bgr_image, "lut": identity_cube},
    )
    assert_success(three_d)
    delta = np.abs(
        three_d.output.images["image"].data.astype(np.int16)
        - bgr_image.data.astype(np.int16)
    )
    assert int(delta.max()) <= 1


@pytest.mark.parametrize(
    "mode",
    ["normal", "multiply", "screen", "overlay", "soft_light", "hard_light", "difference", "add", "subtract"],
)
def test_blend_modes(registry, bgr_image, mode):
    layer = ImageData(
        data=np.flip(bgr_image.data, axis=1).copy(),
        color_space=ColorSpace.BGR,
    )
    result = registry.execute(
        operation="blend_images",
        inputs={"base": bgr_image, "layer": layer},
        params={"mode": mode, "opacity": 0.6},
    )
    images = assert_success(result)
    assert images["image"].shape == bgr_image.shape
    assert images["image"].data.dtype == np.uint8


def test_apply_mask_selects_between_two_images(registry):
    base = ImageData(data=np.zeros((8, 10), dtype=np.uint8), color_space=ColorSpace.GRAY)
    effect = ImageData(data=np.full((8, 10), 200, dtype=np.uint8), color_space=ColorSpace.GRAY)
    mask_data = np.zeros((8, 10), dtype=np.uint8)
    mask_data[:, 5:] = 255
    mask = ImageData(data=mask_data, color_space=ColorSpace.BINARY)
    result = registry.execute(
        operation="apply_mask",
        inputs={"base": base, "effect": effect, "mask": mask},
    )
    output = assert_success(result)["image"].data
    assert np.all(output[:, :5] == 0)
    assert np.all(output[:, 5:] == 200)


def test_arithmetic_weighted_sum_and_bitwise_nor(registry):
    first = ImageData(data=np.array([[30, 200]], dtype=np.uint8), color_space=ColorSpace.GRAY)
    second = ImageData(data=np.array([[10, 100]], dtype=np.uint8), color_space=ColorSpace.GRAY)

    subtract = registry.execute(
        operation="image_arithmetic",
        inputs={"image1": first, "image2": second},
        params={"operation": "subtract"},
    )
    assert np.array_equal(assert_success(subtract)["image"].data, [[20, 100]])

    weighted = registry.execute(
        operation="weighted_sum",
        inputs={"image1": first, "image2": second},
        params={"alpha": 0.25, "beta": 0.75},
    )
    assert np.array_equal(assert_success(weighted)["image"].data, [[15, 125]])

    nor = registry.execute(
        operation="bitwise_operation",
        inputs={"image1": first, "image2": second},
        params={"operation": "nor"},
    )
    assert np.array_equal(
        assert_success(nor)["image"].data,
        np.bitwise_not(np.bitwise_or(first.data, second.data)),
    )


def test_bitwise_not_does_not_require_second_image(registry):
    image = ImageData(data=np.array([[0, 255]], dtype=np.uint8), color_space=ColorSpace.GRAY)
    result = registry.execute(
        operation="bitwise_operation",
        inputs={"image1": image},
        params={"operation": "not"},
    )
    assert np.array_equal(assert_success(result)["image"].data, [[255, 0]])


def test_vignette_and_grain_are_safe_and_reproducible(registry, bgr_image):
    vignette = registry.execute(
        operation="vignette",
        inputs={"image": bgr_image},
        params={"strength": 1.0, "radius": 0.8},
    )
    output = assert_success(vignette)["image"].data
    assert output[0, 0].sum() <= bgr_image.data[0, 0].sum()

    parameters = {"amount": 0.1, "random_seed": 7, "grain_size": 2}
    first = registry.execute(operation="add_grain", inputs={"image": bgr_image}, params=parameters)
    second = registry.execute(operation="add_grain", inputs={"image": bgr_image}, params=parameters)
    assert np.array_equal(
        assert_success(first)["image"].data,
        assert_success(second)["image"].data,
    )


@pytest.mark.parametrize(
    "operation",
    ["edge_preserving_filter", "detail_enhance", "stylization"],
)
def test_single_image_photo_operations(registry, bgr_image, operation):
    result = registry.execute(operation=operation, inputs={"image": bgr_image})
    images = assert_success(result)
    assert images["image"].shape == bgr_image.shape
    assert images["image"].color_space == ColorSpace.BGR


def test_pencil_sketch_returns_gray_and_color(registry, bgr_image):
    result = registry.execute(operation="pencil_sketch", inputs={"image": bgr_image})
    images = assert_success(result)
    assert images["gray"].shape == bgr_image.shape[:2]
    assert images["color"].shape == bgr_image.shape


@pytest.mark.parametrize(
    ("operation", "params"),
    [
        ("color_change", {"red": 1.2}),
        ("illumination_change", {"alpha": 0.3, "beta": 0.5}),
        ("texture_flattening", {"low_threshold": 20, "high_threshold": 40}),
    ],
)
def test_masked_photo_operations(registry, bgr_image, operation, params):
    mask_data = np.zeros(bgr_image.shape[:2], dtype=np.uint8)
    cv2.circle(mask_data, (48, 36), 22, 255, -1)
    mask = ImageData(data=mask_data, color_space=ColorSpace.BINARY)
    result = registry.execute(
        operation=operation,
        inputs={"image": bgr_image, "mask": mask},
        params=params,
    )
    assert assert_success(result)["image"].shape == bgr_image.shape


def test_seamless_clone(registry):
    source_data = np.full((24, 24, 3), (20, 40, 220), dtype=np.uint8)
    cv2.circle(source_data, (12, 12), 8, (20, 220, 40), -1)
    destination_data = np.full((64, 64, 3), 100, dtype=np.uint8)
    mask_data = np.zeros((24, 24), dtype=np.uint8)
    cv2.circle(mask_data, (12, 12), 10, 255, -1)
    source = ImageData(data=source_data, color_space=ColorSpace.BGR)
    destination = ImageData(data=destination_data, color_space=ColorSpace.BGR)
    mask = ImageData(data=mask_data, color_space=ColorSpace.BINARY)
    result = registry.execute(
        operation="seamless_clone",
        inputs={"source": source, "destination": destination, "mask": mask},
        params={"center_x": 32, "center_y": 32, "mode": "mixed"},
    )
    assert assert_success(result)["image"].shape == destination.shape


def test_editing_operations_compose_in_pipeline(bgr_image):
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
        inputs={"image": bgr_image},
    )
    assert result.success is True, result.error
    assert [step.step_id for step in result.steps] == ["tone", "vignette", "grain"]
    assert result.output.images["image"].shape == bgr_image.shape
