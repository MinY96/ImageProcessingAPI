from __future__ import annotations

from ..common import exact_mask_composite, to_bgr
from ..diffusion import DiffusionManager, resolve_prompt_preset
from ..errors import SyntheticValidationError
from .base import GenerationContext, GeneratorOutput


class DiffusionInpaintGenerator:
    def __init__(self, manager: DiffusionManager) -> None:
        self._manager = manager

    def generate(self, context: GenerationContext) -> GeneratorOutput:
        params = context.request.parameters
        model = str(params.get("model", "sdxl_inpaint"))
        preset_key = str(params.get("prompt_preset", "")).strip() or None
        preset = resolve_prompt_preset(preset_key) if preset_key else None
        prompt = str(params.get("prompt", "")).strip()
        if not prompt and preset is not None:
            prompt = preset.prompt
        if not prompt:
            raise SyntheticValidationError(
                "diffusion_inpaint requires parameters.prompt or parameters.prompt_preset"
            )
        negative_prompt = params.get("negative_prompt")
        if negative_prompt is None and preset is not None:
            negative_prompt = preset.negative_prompt
        if negative_prompt is not None:
            negative_prompt = str(negative_prompt)
        source = to_bgr(context.source)
        generated = self._manager.get(model).generate(
            image_bgr=source,
            mask=context.target_mask,
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=context.seed,
            parameters=params,
        )
        feather = context.request.mask.feather_px if context.request.mask else int(params.get("feather_px", 3))
        output = exact_mask_composite(
            source,
            generated,
            context.target_mask,
            feather_px=feather,
        )
        return GeneratorOutput(
            image=output,
            mask=context.target_mask,
            metadata={
                "model": model,
                "prompt_preset": preset_key,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "background_preservation": "outside-mask pixels restored from original",
            },
        )
