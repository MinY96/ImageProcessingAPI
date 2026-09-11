from __future__ import annotations

import time
from collections import Counter
from collections.abc import Mapping
from typing import Any, TypeAlias

from src.registry import OperationRegistry
from src.schemas import (
    ExecutionMetadata,
    ImageData,
    OperationOutput,
    PipelineError,
    PipelineExecutionResult,
    PipelineInputReference,
    PipelineSpec,
    PipelineStepExecution,
    PipelineValueReference,
    StepOutputReference,
)
from src.validators import InputValidationError, InputValidator

from .compiler import CompiledPipeline, PipelineCompiler
from .errors import PipelineValidationError


ReferenceKey: TypeAlias = tuple[str, str, str]


class PipelineExecutor:
    """CompiledPipeline의 step을 Registry를 통해 순서대로 실행한다."""

    def __init__(self, registry: OperationRegistry) -> None:
        self._registry = registry
        self._compiler = PipelineCompiler(registry)

    def compile(self, pipeline: PipelineSpec) -> CompiledPipeline:
        return self._compiler.compile(pipeline)

    def execute(
        self,
        *,
        pipeline: PipelineSpec | CompiledPipeline,
        inputs: Mapping[str, Any] | None = None,
        retain_intermediates: bool = False,
    ) -> PipelineExecutionResult:
        started_at = time.perf_counter()

        try:
            if isinstance(pipeline, CompiledPipeline):
                compiled = (
                    pipeline
                    if pipeline.registry_revision
                    == self._registry.revision
                    else self.compile(pipeline.spec)
                )
            else:
                compiled = self.compile(pipeline)

            if compiled.registry_revision != self._registry.revision:
                compiled = self.compile(compiled.spec)
        except PipelineValidationError as exc:
            error_data = exc.to_dict()
            pipeline_name = pipeline.name
            return self._failure_result(
                pipeline=pipeline_name,
                code=error_data["error"],
                message=str(exc),
                details={"issues": error_data["issues"]},
                started_at=started_at,
            )

        try:
            validated_inputs = InputValidator.validate_slots(
                inputs=dict(inputs or {}),
                slots=compiled.spec.inputs,
                owner_name=compiled.spec.name,
            )
        except InputValidationError as exc:
            error_data = exc.to_dict()
            return self._failure_result(
                pipeline=compiled.spec.name,
                code="pipeline_input_validation_error",
                message=str(exc),
                details={"issues": error_data["issues"]},
                started_at=started_at,
            )

        step_outputs: dict[str, OperationOutput] = {}
        intermediates: dict[str, OperationOutput] = {}
        step_executions: list[PipelineStepExecution] = []
        warnings: list[str] = []
        remaining_uses = self._count_reference_uses(compiled)

        for step in compiled.spec.steps:
            resolved_inputs = {
                name: self._resolve_reference(
                    reference=reference,
                    pipeline_inputs=validated_inputs,
                    step_outputs=step_outputs,
                )[0]
                for name, reference in step.inputs.items()
            }

            result = self._registry.execute(
                operation=step.operation,
                inputs=resolved_inputs,
                params=step.params,
            )

            step_executions.append(
                PipelineStepExecution(
                    step_id=step.id,
                    operation=step.operation,
                    success=result.success,
                    metadata=result.metadata,
                    error=result.error,
                )
            )
            warnings.extend(
                f"{step.id}: {warning}"
                for warning in result.metadata.warnings
            )

            if not result.success:
                assert result.error is not None
                return self._failure_result(
                    pipeline=compiled.spec.name,
                    code="pipeline_step_failed",
                    message=(
                        f"pipeline step failed: {step.id} "
                        f"({step.operation})"
                    ),
                    step_id=step.id,
                    operation=step.operation,
                    details={
                        "cause": result.error.model_dump(mode="json")
                    },
                    steps=step_executions,
                    intermediates=intermediates,
                    warnings=warnings,
                    started_at=started_at,
                )

            if retain_intermediates:
                intermediates[step.id] = result.output

            self._store_needed_outputs(
                step_id=step.id,
                output=result.output,
                remaining_uses=remaining_uses,
                step_outputs=step_outputs,
                retain_intermediates=retain_intermediates,
            )

            self._consume_references(
                references=step.inputs.values(),
                remaining_uses=remaining_uses,
                step_outputs=step_outputs,
                retain_intermediates=retain_intermediates,
            )

        pipeline_output = self._build_pipeline_output(
            bindings=compiled.output_bindings,
            pipeline_inputs=validated_inputs,
            step_outputs=step_outputs,
        )

        return PipelineExecutionResult(
            pipeline=compiled.spec.name,
            success=True,
            output=pipeline_output,
            steps=step_executions,
            intermediates=intermediates,
            metadata=ExecutionMetadata(
                duration_ms=self._elapsed_ms(started_at),
                warnings=warnings,
            ),
        )

    @classmethod
    def _count_reference_uses(
        cls,
        compiled: CompiledPipeline,
    ) -> Counter[ReferenceKey]:
        references = [
            reference
            for step in compiled.spec.steps
            for reference in step.inputs.values()
        ]
        references.extend(compiled.output_bindings.values())
        return Counter(
            cls._reference_key(reference)
            for reference in references
        )

    @staticmethod
    def _reference_key(
        reference: PipelineValueReference,
    ) -> ReferenceKey:
        if isinstance(reference, PipelineInputReference):
            return ("pipeline_input", reference.input_name, "")
        return (
            "step_output",
            reference.step_id,
            reference.output_name,
        )

    @staticmethod
    def _resolve_reference(
        *,
        reference: PipelineValueReference,
        pipeline_inputs: dict[str, Any],
        step_outputs: dict[str, OperationOutput],
    ) -> tuple[Any, bool]:
        if isinstance(reference, PipelineInputReference):
            value = pipeline_inputs[reference.input_name]
            return value, isinstance(value, ImageData)

        output = step_outputs[reference.step_id]
        if reference.output_name in output.images:
            return output.images[reference.output_name], True
        return output.data[reference.output_name], False

    @classmethod
    def _store_needed_outputs(
        cls,
        *,
        step_id: str,
        output: OperationOutput,
        remaining_uses: Counter[ReferenceKey],
        step_outputs: dict[str, OperationOutput],
        retain_intermediates: bool,
    ) -> None:
        if retain_intermediates:
            step_outputs[step_id] = output
            return

        images = {
            name: value
            for name, value in output.images.items()
            if remaining_uses[("step_output", step_id, name)] > 0
        }
        data = {
            name: value
            for name, value in output.data.items()
            if remaining_uses[("step_output", step_id, name)] > 0
        }

        if images or data:
            step_outputs[step_id] = OperationOutput(
                images=images,
                data=data,
            )

    @classmethod
    def _consume_references(
        cls,
        *,
        references,
        remaining_uses: Counter[ReferenceKey],
        step_outputs: dict[str, OperationOutput],
        retain_intermediates: bool,
    ) -> None:
        for reference in references:
            key = cls._reference_key(reference)
            remaining_uses[key] -= 1

            if (
                retain_intermediates
                or key[0] != "step_output"
                or remaining_uses[key] > 0
            ):
                continue

            step_id, output_name = key[1], key[2]
            output = step_outputs.get(step_id)
            if output is None:
                continue

            output.images.pop(output_name, None)
            output.data.pop(output_name, None)

            if not output.images and not output.data:
                step_outputs.pop(step_id, None)

    @classmethod
    def _build_pipeline_output(
        cls,
        *,
        bindings: dict[str, PipelineValueReference],
        pipeline_inputs: dict[str, Any],
        step_outputs: dict[str, OperationOutput],
    ) -> OperationOutput:
        images = {}
        data = {}

        for name, reference in bindings.items():
            value, is_image = cls._resolve_reference(
                reference=reference,
                pipeline_inputs=pipeline_inputs,
                step_outputs=step_outputs,
            )
            if is_image:
                images[name] = value
            else:
                data[name] = value

        return OperationOutput(images=images, data=data)

    @classmethod
    def _failure_result(
        cls,
        *,
        pipeline: str,
        code: str,
        message: str,
        details: dict[str, Any],
        started_at: float,
        step_id: str | None = None,
        operation: str | None = None,
        steps: list[PipelineStepExecution] | None = None,
        intermediates: dict[str, OperationOutput] | None = None,
        warnings: list[str] | None = None,
    ) -> PipelineExecutionResult:
        return PipelineExecutionResult(
            pipeline=pipeline,
            success=False,
            steps=steps or [],
            intermediates=intermediates or {},
            metadata=ExecutionMetadata(
                duration_ms=cls._elapsed_ms(started_at),
                warnings=warnings or [],
            ),
            error=PipelineError(
                code=code,
                message=message,
                step_id=step_id,
                operation=operation,
                details=details,
            ),
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return max(
            0.0,
            (time.perf_counter() - started_at) * 1000.0,
        )
