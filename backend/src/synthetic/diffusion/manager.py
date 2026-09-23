from __future__ import annotations

import importlib.util
from pathlib import Path

from ..errors import SyntheticValidationError
from ..schemas import DiffusionModelStatus
from .flux import FluxFillProvider
from .openvino_sd15 import OpenVINOSD15InpaintProvider
from .sdxl import SDXLInpaintProvider


def _has_modules(*names: str) -> bool:
    try:
        return all(importlib.util.find_spec(name) is not None for name in names)
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


class DiffusionManager:
    def __init__(
        self,
        *,
        cache_dir: Path,
        local_files_only: bool,
        device: str,
        openvino_device: str = "AUTO",
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.local_files_only = bool(local_files_only)
        self.device = device
        self.openvino_device = openvino_device
        self._providers = {
            "sdxl_inpaint": SDXLInpaintProvider(
                cache_dir=self.cache_dir / "sdxl_inpaint",
                local_files_only=self.local_files_only,
                device=self.device,
            ),
            "flux_fill": FluxFillProvider(
                cache_dir=self.cache_dir / "flux_fill",
                local_files_only=self.local_files_only,
                device=self.device,
            ),
            "sd15_openvino_inpaint": OpenVINOSD15InpaintProvider(
                cache_dir=self.cache_dir / "sd15_openvino_inpaint",
                local_files_only=self.local_files_only,
                device=self.openvino_device,
            ),
        }

    @staticmethod
    def dependency_available() -> bool:
        return _has_modules("torch", "diffusers", "transformers", "accelerate")

    @staticmethod
    def openvino_dependency_available() -> bool:
        return OpenVINOSD15InpaintProvider.dependency_available()

    def get(self, model: str):
        try:
            return self._providers[model]
        except KeyError as exc:
            raise SyntheticValidationError(
                f"unknown diffusion model '{model}'; choose one of {sorted(self._providers)}"
            ) from exc

    def statuses(self) -> list[DiffusionModelStatus]:
        torch_dependency = self.dependency_available()
        openvino_dependency = self.openvino_dependency_available()
        openvino_devices = OpenVINOSD15InpaintProvider.available_devices() if openvino_dependency else []
        return [
            DiffusionModelStatus(
                model="sdxl_inpaint",
                display_name="SDXL Inpainting",
                provider="diffusers.AutoPipelineForInpainting",
                model_id=SDXLInpaintProvider.default_model_id,
                dependency_available=torch_dependency,
                loaded=self._providers["sdxl_inpaint"].loaded,
                local_files_only=self.local_files_only,
                cache_dir=str(self.cache_dir / "sdxl_inpaint"),
                device=self.device,
                notes="Default CUDA diffusion provider; recommended for 24 GB-class NVIDIA GPUs.",
            ),
            DiffusionModelStatus(
                model="flux_fill",
                display_name="FLUX.1 Fill dev",
                provider="diffusers.FluxFillPipeline",
                model_id=FluxFillProvider.default_model_id,
                dependency_available=torch_dependency,
                loaded=self._providers["flux_fill"].loaded,
                local_files_only=self.local_files_only,
                cache_dir=str(self.cache_dir / "flux_fill"),
                device=self.device,
                notes="Experimental high-quality provider; uses CPU offload by default on CUDA.",
            ),
            DiffusionModelStatus(
                model="sd15_openvino_inpaint",
                display_name="Stable Diffusion 1.5 Inpainting (OpenVINO)",
                provider="optimum.intel.OVStableDiffusionInpaintPipeline",
                model_id=OpenVINOSD15InpaintProvider.default_model_id,
                dependency_available=openvino_dependency,
                loaded=self._providers["sd15_openvino_inpaint"].loaded,
                local_files_only=self.local_files_only,
                cache_dir=str(self.cache_dir / "sd15_openvino_inpaint"),
                device=self.openvino_device,
                notes=(
                    "Optimized for 512x512 ROI inpainting on Intel CPU/iGPU. "
                    f"OpenVINO devices detected: {', '.join(openvino_devices) if openvino_devices else 'not available/not queried'}."
                ),
            ),
        ]

    def unload(self, model: str | None = None) -> None:
        if model is None:
            for provider in self._providers.values():
                provider.unload()
            return
        self.get(model).unload()
