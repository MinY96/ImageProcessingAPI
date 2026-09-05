import cv2
import numpy as np

from src.pipeline import PipelineExecutor, create_default_pipelines
from src.registry import create_default_registry
from src.schemas import ColorSpace, ImageData, PipelineSpec


BUILTIN_RECIPE_NAMES = [
    "binary_mask_cleanup",
    "cinematic_3d_lut",
    "circle_detection",
    "clean_portrait",
    "color_segmentation",
    "comic_style",
    "document_adaptive",
    "document_otsu",
    "dramatic_detail",
    "edge_thumbnail",
    "film_look",
    "general_edge_detection",
    "line_detection",
    "masked_local_enhancement",
    "natural_enhance",
    "pencil_sketch",
    "reference_difference",
    "seamless_composite",
    "sem_profile_edges",
    "vintage_1d_lut",
]


def _sample_inputs(recipe: PipelineSpec) -> dict:
    height, width = 96, 128
    y, x = np.mgrid[:height, :width]
    bgr = np.stack(
        [
            x * 255 // (width - 1),
            y * 255 // (height - 1),
            (x + y) * 255 // (height + width - 2),
        ],
        axis=2,
    ).astype(np.uint8)
    cv2.rectangle(bgr, (25, 20), (90, 75), (20, 220, 80), 3)
    image = ImageData(data=bgr, color_space=ColorSpace.BGR)
    gray = ImageData(
        data=cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY),
        color_space=ColorSpace.GRAY,
    )
    current_data = gray.data.copy()
    cv2.circle(current_data, (64, 48), 12, 255, -1)
    current = ImageData(data=current_data, color_space=ColorSpace.GRAY)
    mask_data = np.zeros((height, width), dtype=np.uint8)
    cv2.circle(mask_data, (64, 48), 25, 255, -1)
    mask = ImageData(data=mask_data, color_space=ColorSpace.BINARY)

    axis = np.linspace(0.0, 1.0, 4, dtype=np.float32)
    red, green, blue = np.meshgrid(axis, axis, axis, indexing="ij")
    cube = np.stack([red, green, blue], axis=-1)

    source_data = np.full((32, 32, 3), (20, 40, 220), dtype=np.uint8)
    cv2.circle(source_data, (16, 16), 10, (20, 220, 40), -1)
    source = ImageData(data=source_data, color_space=ColorSpace.BGR)
    destination = ImageData(
        data=np.full((480, 640, 3), 100, dtype=np.uint8),
        color_space=ColorSpace.BGR,
    )
    source_mask_data = np.zeros((32, 32), dtype=np.uint8)
    cv2.circle(source_mask_data, (16, 16), 13, 255, -1)
    source_mask = ImageData(data=source_mask_data, color_space=ColorSpace.BINARY)

    values = {}
    for slot in recipe.inputs:
        if slot.name == "image":
            values[slot.name] = image
        elif slot.name == "lut":
            values[slot.name] = (
                cube
                if recipe.name == "cinematic_3d_lut"
                else np.arange(256, dtype=np.float32)
            )
        elif slot.name == "mask":
            values[slot.name] = (
                source_mask if recipe.name == "seamless_composite" else mask
            )
        elif slot.name == "reference":
            values[slot.name] = gray
        elif slot.name == "current":
            values[slot.name] = current
        elif slot.name == "source":
            values[slot.name] = source
        elif slot.name == "destination":
            values[slot.name] = destination
    return values


def test_default_pipeline_catalog_contains_twenty_recipes():
    recipes = create_default_pipelines()
    assert len(recipes) == 20
    assert sorted(recipe.name for recipe in recipes) == BUILTIN_RECIPE_NAMES


def test_all_builtin_recipes_compile_and_json_round_trip():
    executor = PipelineExecutor(create_default_registry())
    for recipe in create_default_pipelines():
        restored = PipelineSpec.model_validate_json(recipe.model_dump_json())
        compiled = executor.compile(restored)
        assert compiled.spec.name == recipe.name


def test_all_builtin_recipes_execute_with_representative_inputs():
    executor = PipelineExecutor(create_default_registry())
    for recipe in create_default_pipelines():
        result = executor.execute(
            pipeline=recipe,
            inputs=_sample_inputs(recipe),
        )
        assert result.success is True, (recipe.name, result.error)
        assert result.output.images or result.output.data
