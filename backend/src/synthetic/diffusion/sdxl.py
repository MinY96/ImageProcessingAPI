from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ..errors import SyntheticDependencyError, SyntheticModelUnavailableError, SyntheticValidationError


class SDXLInpaintProvider:
    model_key = "sdxl_inpaint"
    default_model_id = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"

    def __init__(
        self,
        *,
        cache_dir: Path,
        local_files_only: bool,
        device: str,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.local_files_only = bool(local_files_only)
        self.device = device
        self._pipe = None
        self._loaded_model_id: str | None = None

    @property
    def loaded(self) -> bool:
        return self._pipe is not None

    def _load(self, model_id: str):
        if self._pipe is not None and self._loaded_model_id == model_id:
            return self._pipe
        try:
            import torch
            from diffusers import AutoPipelineForInpainting
        except ImportError as exc:
            raise SyntheticDependencyError(
                "SDXL inpainting requires torch, diffusers, transformers, accelerate, and safetensors"
            ) from exc

        self.unload()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        dtype = torch.float16 if self.device.startswith("cuda") else torch.float32
        kwargs = {
            "torch_dtype": dtype,
            "cache_dir": str(self.cache_dir),
            "local_files_only": self.local_files_only,
        }
        if self.device.startswith("cuda"):
            kwargs["variant"] = "fp16"
        try:
            pipe = AutoPipelineForInpainting.from_pretrained(model_id, **kwargs)
        except Exception as exc:
            mode = "local cache only" if self.local_files_only else "download/cache enabled"
            raise SyntheticModelUnavailableError(
                f"could not load SDXL inpainting model '{model_id}' ({mode}): {exc}"
            ) from exc

        try:
            pipe = pipe.to(self.device)
        except Exception as exc:
            raise SyntheticModelUnavailableError(
                f"could not move SDXL inpainting model to device '{self.device}': {exc}"
            ) from exc
        self._pipe = pipe
        self._loaded_model_id = model_id
        return pipe

    def generate(
        self,
        *,
        image_bgr: np.ndarray,
        mask: np.ndarray,
        prompt: str,
        negative_prompt: str | None,
        seed: int,
        parameters: dict,
    ) -> np.ndarray:
        if not prompt.strip():
            raise SyntheticValidationError("diffusion_inpaint requires parameters.prompt")
        model_id = str(parameters.get("model_id") or self.default_model_id)
        pipe = self._load(model_id)
        import torch

        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_pil = Image.fromarray(rgb)
        mask_pil = Image.fromarray(mask)
        generator_device = self.device if self.device.startswith("cuda") else "cpu"
        generator = torch.Generator(device=generator_device).manual_seed(seed)
        steps = int(np.clip(parameters.get("steps", 25), 1, 100))
        guidance = float(np.clip(parameters.get("guidance_scale", 7.0), 0.0, 30.0))
        strength = float(np.clip(parameters.get("strength", 0.95), 0.0, 1.0))

        kwargs = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "image": image_pil,
            "mask_image": mask_pil,
            "num_inference_steps": steps,
            "guidance_scale": guidance,
            "strength": strength,
            "generator": generator,
        }
        try:
            result = pipe(**kwargs).images[0]
        except Exception as exc:
            raise SyntheticModelUnavailableError(f"SDXL inpainting inference failed: {exc}") from exc
        out_rgb = np.asarray(result.convert("RGB"), dtype=np.uint8)
        out_bgr = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)
        if out_bgr.shape[:2] != image_bgr.shape[:2]:
            out_bgr = cv2.resize(
                out_bgr,
                (image_bgr.shape[1], image_bgr.shape[0]),
                interpolation=cv2.INTER_LANCZOS4,
            )
        return out_bgr

    def unload(self) -> None:
        self._pipe = None
        self._loaded_model_id = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
