from dataclasses import dataclass

from src.analysis import ImageAnalyzer
from src.labeling import LabelService
from src.evaluation import EvaluationService, TestDatasetService
from src.machine_learning import ModelRegistry
from src.pipeline import PipelineCatalog, PipelineExecutor
from src.recipe import RecipeService
from src.registry import OperationRegistry
from src.workflow import (
    FeatureRegistry,
    ScalarOperatorRegistry,
    WorkflowCatalog,
    WorkflowExecutor,
)

from .config import ApiSettings


@dataclass(frozen=True, slots=True)
class ApiServices:
    registry: OperationRegistry
    feature_registry: FeatureRegistry
    scalar_operator_registry: ScalarOperatorRegistry
    image_analyzer: ImageAnalyzer
    model_registry: ModelRegistry
    pipeline_executor: PipelineExecutor
    pipeline_catalog: PipelineCatalog
    workflow_executor: WorkflowExecutor
    workflow_catalog: WorkflowCatalog
    recipe_service: RecipeService
    label_service: LabelService
    test_dataset_service: TestDatasetService
    evaluation_service: EvaluationService
    settings: ApiSettings
