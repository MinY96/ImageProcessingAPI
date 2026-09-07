from dataclasses import dataclass

from src.analysis import ImageAnalyzer
from src.labeling import LabelService
from src.machine_learning import ModelRegistry
from src.pipeline import PipelineCatalog, PipelineExecutor
from src.recipe import RecipeService
from src.registry import OperationRegistry

from .config import ApiSettings


@dataclass(frozen=True, slots=True)
class ApiServices:
    registry: OperationRegistry
    image_analyzer: ImageAnalyzer
    model_registry: ModelRegistry
    pipeline_executor: PipelineExecutor
    pipeline_catalog: PipelineCatalog
    recipe_service: RecipeService
    label_service: LabelService
    settings: ApiSettings
