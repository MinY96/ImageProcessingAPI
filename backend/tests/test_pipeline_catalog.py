import pytest

from src.pipeline import (
    DuplicatePipelineError,
    PipelineCatalog,
    PipelineExecutor,
    PipelineNotFoundError,
    pipeline_input,
)
from src.registry import create_default_registry
from src.schemas import (
    InputKind,
    InputSlotSpec,
    PipelineSpec,
    PipelineStepSpec,
)


def make_pipeline() -> PipelineSpec:
    return PipelineSpec(
        name="blur_pipeline",
        display_name="Blur Pipeline",
        inputs=[
            InputSlotSpec(name="image", kind=InputKind.IMAGE)
        ],
        steps=[
            PipelineStepSpec(
                id="blur",
                operation="gaussian_blur",
                inputs={"image": pipeline_input("image")},
            )
        ],
    )


def test_pipeline_catalog_registers_and_lists():
    catalog = PipelineCatalog(
        PipelineExecutor(create_default_registry())
    )
    catalog.register(make_pipeline())

    assert catalog.contains("blur_pipeline")
    assert catalog.get_spec("blur_pipeline").name == "blur_pipeline"
    assert [item.name for item in catalog.list_specs()] == [
        "blur_pipeline"
    ]


def test_pipeline_catalog_rejects_duplicate():
    catalog = PipelineCatalog(
        PipelineExecutor(create_default_registry())
    )
    catalog.register(make_pipeline())

    with pytest.raises(DuplicatePipelineError):
        catalog.register(make_pipeline())


def test_pipeline_catalog_missing_name():
    catalog = PipelineCatalog(
        PipelineExecutor(create_default_registry())
    )

    with pytest.raises(PipelineNotFoundError):
        catalog.get("missing")
