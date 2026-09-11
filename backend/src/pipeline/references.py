from src.schemas import (
    PipelineInputReference,
    StepOutputReference,
)


def pipeline_input(name: str) -> PipelineInputReference:
    return PipelineInputReference(input_name=name)


def step_output(
    step_id: str,
    output_name: str = "image",
) -> StepOutputReference:
    return StepOutputReference(
        step_id=step_id,
        output_name=output_name,
    )
