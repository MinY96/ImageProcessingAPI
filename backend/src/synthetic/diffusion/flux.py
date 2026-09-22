from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ..errors import SyntheticDependencyError, SyntheticModelUnavailableError, SyntheticValidationError


class FluxFillProvider:
    model_key = "flux_fill"
    default_model_id = "black-forest-labs/FLUX.1-Fill-dev"

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
            from diffusers import FluxFillPipeline
        except ImportError as exc:
            raise SyntheticDependencyError(
                "FLUX Fill requires torch, diffusers, transformers, accelerate, and safetensors"
            ) from exc

        self.unload()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        dtype = torch.bfloat16 if self.device.startswith("cuda") else torch.float32
        try:
            pipe = FluxFillPipeline.from_pretrained(
                model_id,
                torch_dtype=dtype,
                cache_dir=str(self.cache_dir),
                local_files_only=self.local_files_only,
            )
        except Exception as exc:
            mode = "local cache only" if self.local_files_only else "download/cache enabled"
            raise SyntheticModelUnavailableError(
                f"could not load FLUX Fill model '{model_id}' ({mode}): {exc}"
            ) from exc

        try:
            if self.device.startswith("cuda"):
                # FLUX Fill is large; CPU offload is safer on 24 GB-class GPUs.
                pipe.enable_model_cpu_offload()
            else:
                pipe = pipe.to(self.device)
        except Exception as exc:
            raise SyntheticModelUnavailableError(
                f"could not configure FLUX Fill for device '{self.device}': {exc}"
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
        generator = torch.Generator(device="cpu").manual_seed(seed)
        steps = int(np.clip(parameters.get("steps", 28), 1, 100))
        guidance = float(np.clip(parameters.get("guidance_scale", 30.0), 0.0, 100.0))
        kwargs = {
            "prompt": prompt,
            "image": image_pil,
            "mask_image": mask_pil,
            "num_inference_steps": steps,
            "guidance_scale": guidance,
            "generator": generator,
        }
        # FluxFillPipeline does not consistently expose negative_prompt across releases.
        if negative_prompt and bool(parameters.get("use_negative_prompt", False)):
            kwargs["negative_prompt"] = negative_prompt
        try:
            result = pipe(**kwargs).images[0]
        except Exception as exc:
            raise SyntheticModelUnavailableError(f"FLUX Fill inference failed: {exc}") from exc
        out_rgb = np.asarray(result.convert("RGB"), dtype=np.uint8)
        out_bgr = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)
        if out_bgr.shape[:2] != image_bgr.shape[:2]:
            out_bgr = cv2.resize(out_bgr, (image_bgr.shape[1], image_bgr.shape[0]), interpolation=cv2.INTER_LANCZOS4)
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
