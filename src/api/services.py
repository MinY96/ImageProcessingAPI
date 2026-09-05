from dataclasses import dataclass

from src.machine_learning import ModelRegistry
from src.pipeline import PipelineCatalog, PipelineExecutor
from src.registry import OperationRegistry

from .config import ApiSettings


@dataclass(frozen=True, slots=True)
class ApiServices:
    registry: OperationRegistry
    model_registry: ModelRegistry
    pipeline_executor: PipelineExecutor
    pipeline_catalog: PipelineCatalog
    settings: ApiSettings
