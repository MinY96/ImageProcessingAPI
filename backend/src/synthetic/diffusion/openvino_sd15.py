from __future__ import annotations

import gc
import importlib.util
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from ..errors import SyntheticDependencyError, SyntheticModelUnavailableError, SyntheticValidationError


class OpenVINOSD15InpaintProvider:
    """Stable Diffusion 1.5 inpainting via Optimum Intel / OpenVINO.

    The provider is intentionally optimized around a 512x512 working image. Source
    ROIs with another shape are resized to the configured working size for inference
    and restored to the original shape before returning. The outer synthetic layer
    still restores pixels outside the requested mask exactly.
    """

    model_key = "sd15_openvino_inpaint"
    default_model_id = "stable-diffusion-v1-5/stable-diffusion-inpainting"
    default_input_size = 512

    def __init__(
        self,
        *,
        cache_dir: Path,
        local_files_only: bool,
        device: str = "AUTO",
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.local_files_only = bool(local_files_only)
        self.device = str(device or "AUTO")
        self._pipe = None
        self._loaded_model_id: str | None = None
        self._loaded_device: str | None = None
        self._loaded_input_size: int | None = None

    @property
    def loaded(self) -> bool:
        return self._pipe is not None

    @staticmethod
    def dependency_available() -> bool:
        try:
            return all(
                importlib.util.find_spec(name) is not None
                for name in ("openvino", "optimum.intel", "diffusers", "transformers")
            )
        except (ImportError, ModuleNotFoundError, ValueError):
            return False

    @staticmethod
    def available_devices() -> list[str]:
        try:
            import openvino as ov

            return list(ov.Core().available_devices)
        except Exception:
            return []

    @staticmethod
    def _pipeline_class():
        try:
            # Optimum Intel 2.x generic auto-class (preferred).
            from optimum.intel import OVPipelineForInpainting

            return OVPipelineForInpainting
        except (ImportError, AttributeError):
            try:
                # Compatibility with Optimum Intel 1.x.
                from optimum.intel import OVStableDiffusionInpaintPipeline

                return OVStableDiffusionInpaintPipeline
            except (ImportError, AttributeError) as exc:
                raise SyntheticDependencyError(
                    "OpenVINO SD1.5 inpainting requires OpenVINO and Optimum Intel. "
                    "Install with: python -m pip install -r requirements-openvino-diffusion.txt"
                ) from exc

    @staticmethod
    def _normalize_device(device: str) -> str:
        normalized = device.strip().upper()
        if not normalized:
            return "AUTO"
        if normalized == "IGPU":
            return "GPU"
        return normalized

    def _resolve_device(self, requested: str | None) -> str:
        target = self._normalize_device(requested or self.device)
        if target == "AUTO":
            # OpenVINO AUTO will choose among available devices at compile time.
            return "AUTO"
        available = self.available_devices()
        if target == "GPU" and not any(item == "GPU" or item.startswith("GPU.") for item in available):
            raise SyntheticModelUnavailableError(
                f"OpenVINO GPU was requested but no GPU device is available; detected={available or ['none']}"
            )
        if target.startswith("GPU.") and target not in available:
            raise SyntheticModelUnavailableError(
                f"OpenVINO device '{target}' is not available; detected={available or ['none']}"
            )
        if target == "CPU" and available and "CPU" not in available:
            raise SyntheticModelUnavailableError(
                f"OpenVINO CPU was requested but CPU is not available; detected={available}"
            )
        return target

    def _export_dir(self, model_id: str, input_size: int) -> Path:
        safe_name = model_id.replace("/", "__").replace("\\", "__")
        return self.cache_dir / "exported" / f"{safe_name}_{input_size}x{input_size}"

    @staticmethod
    def _looks_exported(path: Path) -> bool:
        return (path / "model_index.json").is_file() and any(path.rglob("openvino_model.xml"))

    def _load(self, *, model_id: str, device: str, input_size: int, export_if_missing: bool):
        if (
            self._pipe is not None
            and self._loaded_model_id == model_id
            and self._loaded_device == device
            and self._loaded_input_size == input_size
        ):
            return self._pipe

        if input_size < 64 or input_size > 2048 or input_size % 8 != 0:
            raise SyntheticValidationError("OpenVINO diffusion input_size must be 64..2048 and divisible by 8")

        if not self.dependency_available():
            raise SyntheticDependencyError(
                "OpenVINO SD1.5 inpainting dependencies are unavailable. Install with: "
                "python -m pip install -r requirements-openvino-diffusion.txt"
            )

        PipelineClass = self._pipeline_class()
        self.unload()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        export_dir = self._export_dir(model_id, input_size)

        try:
            if self._looks_exported(export_dir):
                pipe = PipelineClass.from_pretrained(
                    str(export_dir),
                    device=device,
                    compile=False,
                    local_files_only=True,
                )
            else:
                if self.local_files_only and not export_if_missing:
                    raise SyntheticModelUnavailableError(
                        "OpenVINO SD1.5 model has not been prepared locally. Run "
                        "'python scripts/prepare_openvino_sd15_inpaint.py' on a machine with model access, "
                        f"or set parameters.export_if_missing=true. Expected export directory: {export_dir}"
                    )
                pipe = PipelineClass.from_pretrained(
                    model_id,
                    export=True,
                    compile=False,
                    device=device,
                    cache_dir=str(self.cache_dir / "hf_cache"),
                    local_files_only=self.local_files_only,
                )
                # Static shape is preferable for repeated 512x512 office-PC inference.
                if hasattr(pipe, "reshape"):
                    pipe.reshape(
                        batch_size=1,
                        height=input_size,
                        width=input_size,
                        num_images_per_prompt=1,
                    )
                export_dir.mkdir(parents=True, exist_ok=True)
                pipe.save_pretrained(str(export_dir))

            # Reloaded exports may still be dynamic. Shape once before compile when supported.
            if hasattr(pipe, "reshape"):
                pipe.reshape(
                    batch_size=1,
                    height=input_size,
                    width=input_size,
                    num_images_per_prompt=1,
                )
            if hasattr(pipe, "compile"):
                pipe.compile()
        except SyntheticModelUnavailableError:
            raise
        except Exception as exc:
            mode = "local cache only" if self.local_files_only else "download/export enabled"
            raise SyntheticModelUnavailableError(
                f"could not load/compile OpenVINO SD1.5 inpainting model '{model_id}' "
                f"on device '{device}' ({mode}): {exc}"
            ) from exc

        self._pipe = pipe
        self._loaded_model_id = model_id
        self._loaded_device = device
        self._loaded_input_size = input_size
        return pipe

    def generate(
        self,
        *,
        image_bgr: np.ndarray,
        mask: np.ndarray,
        prompt: str,
        negative_prompt: str | None,
        seed: int,
        parameters: dict[str, Any],
    ) -> np.ndarray:
        if not prompt.strip():
            raise SyntheticValidationError("diffusion_inpaint requires parameters.prompt or prompt_preset")

        model_id = str(parameters.get("model_id") or self.default_model_id)
        input_size = int(parameters.get("input_size", self.default_input_size))
        device = self._resolve_device(str(parameters.get("device") or self.device))
        export_if_missing = bool(parameters.get("export_if_missing", not self.local_files_only))
        pipe = self._load(
            model_id=model_id,
            device=device,
            input_size=input_size,
            export_if_missing=export_if_missing,
        )

        original_h, original_w = image_bgr.shape[:2]
        if mask.shape[:2] != (original_h, original_w):
            raise SyntheticValidationError("diffusion target mask shape must match source image")

        working_bgr = cv2.resize(
            image_bgr,
            (input_size, input_size),
            interpolation=cv2.INTER_AREA if max(original_h, original_w) >= input_size else cv2.INTER_CUBIC,
        )
        working_mask = cv2.resize(mask, (input_size, input_size), interpolation=cv2.INTER_NEAREST)
        working_mask = np.where(working_mask > 0, 255, 0).astype(np.uint8)

        image_pil = Image.fromarray(cv2.cvtColor(working_bgr, cv2.COLOR_BGR2RGB))
        mask_pil = Image.fromarray(working_mask, mode="L")

        steps = int(np.clip(parameters.get("steps", 20), 1, 100))
        guidance = float(np.clip(parameters.get("guidance_scale", 7.0), 0.0, 30.0))
        strength = float(np.clip(parameters.get("strength", 0.85), 0.0, 1.0))

        # Optimum Intel accepts NumPy or PyTorch random generators. NumPy avoids adding
        # a hard torch runtime dependency when an already-exported OpenVINO model is used.
        generator = np.random.RandomState(seed)
        kwargs = {
            "prompt": prompt,
            "image": image_pil,
            "mask_image": mask_pil,
            "num_inference_steps": steps,
            "guidance_scale": guidance,
            "strength": strength,
            "generator": generator,
            "height": input_size,
            "width": input_size,
            "num_images_per_prompt": 1,
        }
        if negative_prompt:
            kwargs["negative_prompt"] = negative_prompt

        try:
            result = pipe(**kwargs).images[0]
        except Exception as exc:
            raise SyntheticModelUnavailableError(
                f"OpenVINO SD1.5 inpainting inference failed on device '{device}': {exc}"
            ) from exc

        out_rgb = np.asarray(result.convert("RGB"), dtype=np.uint8)
        out_bgr = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)
        if out_bgr.shape[:2] != (original_h, original_w):
            out_bgr = cv2.resize(
                out_bgr,
                (original_w, original_h),
                interpolation=cv2.INTER_LANCZOS4,
            )
        return np.ascontiguousarray(out_bgr)

    def unload(self) -> None:
        pipe = self._pipe
        self._pipe = None
        self._loaded_model_id = None
        self._loaded_device = None
        self._loaded_input_size = None
        if pipe is not None:
            try:
                if hasattr(pipe, "clear_requests"):
                    pipe.clear_requests()
            except Exception:
                pass
        del pipe
        gc.collect()
