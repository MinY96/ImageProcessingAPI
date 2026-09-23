from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from src.schemas import ImageData

from .common import difference_image, image_data_bgr, image_data_mask, to_bgr, to_gray_mask
from .diffusion import DiffusionManager, list_prompt_presets
from .errors import SyntheticValidationError
from .generators import (
    AlphaBlendGenerator,
    AssetCompositeGenerator,
    CutPasteGenerator,
    DiffusionInpaintGenerator,
    GenerationContext,
    ProceduralGenerator,
    SeamlessCloneGenerator,
)
from .masks import resolve_target_mask
from .models import SyntheticCandidate, SyntheticGenerationResult
from .schemas import (
    DiffusionModelStatus,
    DiffusionPromptPreset,
    SyntheticAssetCreateRequest,
    SyntheticAssetSummary,
    SyntheticCandidateMetadata,
    SyntheticGenerateRequest,
    SyntheticMethod,
    SyntheticMethodInfo,
    SyntheticQualityMetrics,
)
from .store import SyntheticAssetData, SyntheticAssetStore


_METHOD_INFO = [
    SyntheticMethodInfo(
        method=SyntheticMethod.PROCEDURAL,
        display_name="Procedural",
        description="Generate blobs, stains, droplets, cracks, specks, or texture anomalies from masks.",
    ),
    SyntheticMethodInfo(
        method=SyntheticMethod.CUT_PASTE,
        display_name="CutPaste",
        description="Copy a source/asset patch into a target region with scale and rotation controls.",
        supports_asset=True,
    ),
    SyntheticMethodInfo(
        method=SyntheticMethod.ALPHA_BLEND,
        display_name="Alpha Blend",
        description="Blend a defect asset into the target region with configurable opacity.",
        requires_asset=True,
        supports_asset=True,
    ),
    SyntheticMethodInfo(
        method=SyntheticMethod.SEAMLESS_CLONE,
        display_name="Poisson / Seamless Clone",
        description="Use OpenCV seamlessClone to adapt an asset to local illumination and gradients.",
        requires_asset=True,
        supports_asset=True,
    ),
    SyntheticMethodInfo(
        method=SyntheticMethod.ASSET_COMPOSITE,
        display_name="Asset Composite",
        description="Composite an asset with color/noise/blur matching for CCTV-like defect synthesis.",
        requires_asset=True,
        supports_asset=True,
    ),
    SyntheticMethodInfo(
        method=SyntheticMethod.DIFFUSION_INPAINT,
        display_name="Diffusion Inpainting",
        description=(
            "Generate a localized defect inside a mask using SDXL, FLUX Fill, or "
            "OpenVINO Stable Diffusion 1.5 Inpainting."
        ),
        optional_dependencies=[
            "diffusers",
            "transformers",
            "accelerate",
            "safetensors",
            "openvino",
            "optimum-intel",
        ],
    ),
]


class SyntheticService:
    def __init__(
        self,
        *,
        asset_store: SyntheticAssetStore,
        diffusion_manager: DiffusionManager,
        max_candidates: int = 16,
    ) -> None:
        self._asset_store = asset_store
        self._diffusion_manager = diffusion_manager
        self._max_candidates = max_candidates
        self._generators = {
            SyntheticMethod.PROCEDURAL: ProceduralGenerator(),
            SyntheticMethod.CUT_PASTE: CutPasteGenerator(),
            SyntheticMethod.ALPHA_BLEND: AlphaBlendGenerator(),
            SyntheticMethod.SEAMLESS_CLONE: SeamlessCloneGenerator(),
            SyntheticMethod.ASSET_COMPOSITE: AssetCompositeGenerator(),
            SyntheticMethod.DIFFUSION_INPAINT: DiffusionInpaintGenerator(diffusion_manager),
        }

    def list_methods(self) -> list[SyntheticMethodInfo]:
        return [item.model_copy(deep=True) for item in _METHOD_INFO]

    def diffusion_status(self) -> list[DiffusionModelStatus]:
        return self._diffusion_manager.statuses()

    def diffusion_prompt_presets(self) -> list[DiffusionPromptPreset]:
        return [
            DiffusionPromptPreset(
                key=item.key,
                display_name=item.display_name,
                prompt=item.prompt,
                negative_prompt=item.negative_prompt,
            )
            for item in list_prompt_presets()
        ]

    def unload_diffusion(self, model: str | None = None) -> None:
        self._diffusion_manager.unload(model)

    def list_assets(self, *, category: str | None = None, search: str | None = None) -> list[SyntheticAssetSummary]:
        items = self._asset_store.list()
        if category:
            normalized = category.casefold().strip()
            items = [item for item in items if item.category.casefold() == normalized]
        if search:
            token = search.casefold().strip()
            items = [
                item for item in items
                if token in " ".join(
                    [item.asset_id, item.name, item.category, item.description or "", " ".join(item.tags)]
                ).casefold()
            ]
        return items

    def add_asset(
        self,
        request: SyntheticAssetCreateRequest,
        *,
        image: ImageData,
        mask: ImageData | None,
    ) -> SyntheticAssetSummary:
        if mask is not None:
            to_gray_mask(mask, width=image.width, height=image.height, name="asset_mask")
        return self._asset_store.save(request, image=image, mask=mask)

    def get_asset(self, asset_id: str) -> SyntheticAssetData:
        return self._asset_store.get(asset_id)

    def delete_asset(self, asset_id: str) -> None:
        self._asset_store.delete(asset_id)

    def generate(
        self,
        request: SyntheticGenerateRequest,
        *,
        source: ImageData,
        target_mask: ImageData | None = None,
        asset: ImageData | None = None,
        asset_mask: ImageData | None = None,
    ) -> SyntheticGenerationResult:
        if request.count > self._max_candidates:
            raise SyntheticValidationError(
                f"candidate count exceeds server limit: {request.count} > {self._max_candidates}"
            )
        if source.width * source.height <= 0:
            raise SyntheticValidationError("source image is empty")
        source_bgr = to_bgr(source)

        stored_asset: SyntheticAssetData | None = None
        if request.asset_id is not None:
            if asset is not None:
                raise SyntheticValidationError("use either asset_id or uploaded asset_image, not both")
            stored_asset = self._asset_store.get(request.asset_id)
            asset = stored_asset.image
            if asset_mask is None:
                asset_mask = stored_asset.mask

        info = next(item for item in _METHOD_INFO if item.method == request.method)
        if info.requires_asset and asset is None:
            raise SyntheticValidationError(f"{request.method.value} requires asset_id or asset_image")

        base_seed = request.seed if request.seed is not None else int(time.time_ns() % 2_147_483_647)
        generator = self._generators[request.method]
        candidates: list[SyntheticCandidate] = []

        for index in range(request.count):
            seed = int((base_seed + index) % 2_147_483_647)
            mask_array, resolved_mask_spec = resolve_target_mask(
                source=source,
                uploaded_mask=target_mask,
                spec=request.mask,
                seed=seed,
            )
            context = GenerationContext(
                source=source,
                target_mask=mask_array,
                request=request,
                seed=seed,
                asset=asset,
                asset_mask=asset_mask,
            )
            generated = generator.generate(context)
            generated_bgr = np.ascontiguousarray(generated.image)
            generated_mask = np.where(generated.mask > 0, 255, 0).astype(np.uint8)
            quality = self._quality(source_bgr, generated_bgr, generated_mask)
            candidates.append(
                SyntheticCandidate(
                    image=image_data_bgr(generated_bgr, name=f"synthetic_{index:02d}.png"),
                    mask=image_data_mask(generated_mask, name=f"mask_{index:02d}.png"),
                    difference=difference_image(source_bgr, generated_bgr),
                    metadata=SyntheticCandidateMetadata(
                        index=index,
                        seed=seed,
                        method=request.method,
                        defect_type=request.defect_type,
                        severity=request.severity,
                        generator_metadata={
                            **generated.metadata,
                            "mask_type": resolved_mask_spec.type.value,
                            "asset_id": request.asset_id,
                        },
                        quality=quality,
                    ),
                )
            )

        return SyntheticGenerationResult(
            candidates=candidates,
            request_metadata={
                "method": request.method.value,
                "defect_type": request.defect_type,
                "count": request.count,
                "seed": base_seed,
                "asset_id": request.asset_id,
            },
        )

    @staticmethod
    def _quality(original: np.ndarray, generated: np.ndarray, mask: np.ndarray) -> SyntheticQualityMetrics:
        diff = cv2.absdiff(original, generated).astype(np.float32)
        pixel_diff = diff.mean(axis=2)
        inside = mask > 0
        outside = ~inside
        changed = np.any(diff > 0, axis=2)
        outside_values = pixel_diff[outside]
        inside_values = pixel_diff[inside]
        return SyntheticQualityMetrics(
            changed_area_ratio=float(changed.mean()),
            outside_mask_mean_abs_diff=float(outside_values.mean()) if outside_values.size else 0.0,
            outside_mask_max_abs_diff=float(outside_values.max()) if outside_values.size else 0.0,
            inside_mask_mean_abs_diff=float(inside_values.mean()) if inside_values.size else 0.0,
        )
