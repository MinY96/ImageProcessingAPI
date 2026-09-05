from src.schemas import PipelineSpec

from .recipes import create_builtin_recipes


def create_default_pipelines() -> list[PipelineSpec]:
    """API에서 바로 조회하고 실행할 수 있는 기본 Pipeline을 생성한다."""
    return create_builtin_recipes()
