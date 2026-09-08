"""Built-in Graph Recipe를 Python에서 직접 실행하는 최소 예제."""

import numpy as np

from src.pipeline import PipelineCatalog, PipelineExecutor, create_default_pipelines
from src.registry import create_default_registry
from src.schemas import ColorSpace, ImageData
from src.workflow import (
    WorkflowCatalog,
    WorkflowExecutor,
    create_builtin_graph_recipes,
    create_default_feature_registry,
    create_default_scalar_operator_registry,
)


def create_runtime():
    operation_registry = create_default_registry()
    pipeline_executor = PipelineExecutor(operation_registry)
    pipeline_catalog = PipelineCatalog(pipeline_executor)
    for pipeline in create_default_pipelines():
        pipeline_catalog.register(pipeline)

    workflow_executor = WorkflowExecutor(
        registry=operation_registry,
        feature_registry=create_default_feature_registry(),
        operator_registry=create_default_scalar_operator_registry(),
        pipeline_executor=pipeline_executor,
        pipeline_catalog=pipeline_catalog,
    )
    workflow_catalog = WorkflowCatalog(workflow_executor)
    workflow_executor.attach_workflow_catalog(workflow_catalog)
    for graph in create_builtin_graph_recipes():
        workflow_catalog.register(graph)
    return workflow_executor, workflow_catalog


def main() -> None:
    executor, catalog = create_runtime()
    image = np.zeros((240, 320), dtype=np.uint8)
    image[60:180, 90:230] = 220
    input_image = ImageData(data=image, color_space=ColorSpace.GRAY, name="demo")

    result = executor.execute(
        recipe=catalog.get("rule_branch_binary_score"),
        inputs={"image": input_image},
        retain_intermediates=False,
    )
    print("success:", result.success)
    print("data:", result.output.data)


if __name__ == "__main__":
    main()
