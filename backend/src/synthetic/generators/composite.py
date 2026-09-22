from __future__ import annotations

import cv2
import numpy as np

from ..common import (
    apply_noise_match,
    exact_mask_composite,
    local_color_match,
    mask_bbox,
    to_bgr,
)
from ..errors import SyntheticValidationError
from .base import GenerationContext, GeneratorOutput


def _asset_mask_array(context: GenerationContext, asset: np.ndarray) -> np.ndarray:
    if context.asset_mask is None:
        return np.full(asset.shape[:2], 255, dtype=np.uint8)
    from ..common import to_gray_mask

    return to_gray_mask(
        context.asset_mask,
        width=context.asset.width if context.asset is not None else asset.shape[1],
        height=context.asset.height if context.asset is not None else asset.shape[0],
        name="asset_mask",
    )


def _rotate_with_mask(image: np.ndarray, mask: np.ndarray, angle: float) -> tuple[np.ndarray, np.ndarray]:
    if abs(angle) < 1e-6:
        return image, mask
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    nw = max(1, int(h * sin + w * cos))
    nh = max(1, int(h * cos + w * sin))
    matrix[0, 2] += nw / 2.0 - w / 2.0
    matrix[1, 2] += nh / 2.0 - h / 2.0
    return (
        cv2.warpAffine(image, matrix, (nw, nh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101),
        cv2.warpAffine(mask, matrix, (nw, nh), flags=cv2.INTER_NEAREST, borderValue=0),
    )


def _fit_asset_to_target(context: GenerationContext, *, auto_match: bool) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    if context.asset is None:
        raise SyntheticValidationError(f"{context.request.method.value} requires an asset image")
    asset = to_bgr(context.asset, name="asset")
    asset_mask = _asset_mask_array(context, asset)
    x1, y1, x2, y2 = mask_bbox(context.target_mask)
    target_w = max(1, x2 - x1)
    target_h = max(1, y2 - y1)
    params = context.request.parameters
    scale = float(np.clip(params.get("scale", 1.0), 0.05, 8.0))
    fitted_w = max(1, int(round(target_w * scale)))
    fitted_h = max(1, int(round(target_h * scale)))
    asset = cv2.resize(asset, (fitted_w, fitted_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    asset_mask = cv2.resize(asset_mask, (fitted_w, fitted_h), interpolation=cv2.INTER_NEAREST)
    angle = float(params.get("rotation_deg", 0.0))
    asset, asset_mask = _rotate_with_mask(asset, asset_mask, angle)

    # Recenter transformed asset over target-mask bbox and clip to canvas.
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    ax1 = center_x - asset.shape[1] // 2
    ay1 = center_y - asset.shape[0] // 2
    ax2 = ax1 + asset.shape[1]
    ay2 = ay1 + asset.shape[0]

    src_x1 = max(0, -ax1)
    src_y1 = max(0, -ay1)
    src_x2 = asset.shape[1] - max(0, ax2 - context.source.width)
    src_y2 = asset.shape[0] - max(0, ay2 - context.source.height)
    dst_x1 = max(0, ax1)
    dst_y1 = max(0, ay1)
    dst_x2 = dst_x1 + max(0, src_x2 - src_x1)
    dst_y2 = dst_y1 + max(0, src_y2 - src_y1)
    if src_x2 <= src_x1 or src_y2 <= src_y1:
        raise SyntheticValidationError("transformed asset falls outside the source image")
    asset = asset[src_y1:src_y2, src_x1:src_x2]
    asset_mask = asset_mask[src_y1:src_y2, src_x1:src_x2]

    source = to_bgr(context.source)
    if auto_match:
        patch = source[dst_y1:dst_y2, dst_x1:dst_x2]
        color_strength = float(np.clip(params.get("color_match", 0.65), 0.0, 1.0))
        noise_strength = float(np.clip(params.get("noise_match", 0.25), 0.0, 2.0))
        asset = local_color_match(asset, patch, strength=color_strength)
        asset = apply_noise_match(asset, patch, strength=noise_strength, rng=np.random.default_rng(context.seed))
        blur_sigma = float(np.clip(params.get("blur_sigma", 0.0), 0.0, 16.0))
        if blur_sigma > 0:
            asset = cv2.GaussianBlur(asset, (0, 0), blur_sigma)
    return asset, asset_mask, (dst_x1, dst_y1, dst_x2, dst_y2)


class CutPasteGenerator:
    def generate(self, context: GenerationContext) -> GeneratorOutput:
        # If no explicit asset is supplied, crop a patch from the source image.
        if context.asset is None:
            source = to_bgr(context.source)
            params = context.request.parameters
            rect = params.get("source_rect")
            if rect is None:
                x1, y1, x2, y2 = mask_bbox(context.target_mask)
                w, h = x2 - x1, y2 - y1
                sx1 = int(np.clip(x1 - w * 1.25, 0, max(0, source.shape[1] - w)))
                sy1 = int(np.clip(y1, 0, max(0, source.shape[0] - h)))
                rect = [sx1, sy1, w, h]
            if not isinstance(rect, (list, tuple)) or len(rect) != 4:
                raise SyntheticValidationError("source_rect must be [x, y, width, height]")
            x, y, w, h = [int(v) for v in rect]
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > source.shape[1] or y + h > source.shape[0]:
                raise SyntheticValidationError("source_rect is outside the source image")
            from src.schemas import ColorSpace, ImageData
            context = GenerationContext(
                source=context.source,
                target_mask=context.target_mask,
                request=context.request,
                seed=context.seed,
                asset=ImageData(data=source[y:y+h, x:x+w].copy(), color_space=ColorSpace.BGR, name="self_patch"),
                asset_mask=None,
            )
        asset, asset_mask, bounds = _fit_asset_to_target(context, auto_match=False)
        source = to_bgr(context.source)
        x1, y1, x2, y2 = bounds
        region = source[y1:y2, x1:x2].astype(np.float32)
        opacity = float(np.clip(context.request.parameters.get("opacity", 1.0), 0.0, 1.0))
        alpha = (asset_mask.astype(np.float32) / 255.0 * opacity)[..., None]
        pasted = region * (1.0 - alpha) + asset.astype(np.float32) * alpha
        generated = source.copy()
        generated[y1:y2, x1:x2] = np.clip(pasted, 0, 255).astype(np.uint8)
        placed_mask = np.zeros(context.target_mask.shape, dtype=np.uint8)
        placed_mask[y1:y2, x1:x2] = np.maximum(placed_mask[y1:y2, x1:x2], asset_mask)
        effective_mask = cv2.bitwise_and(placed_mask, context.target_mask)
        if not np.any(effective_mask):
            effective_mask = placed_mask
        feather = context.request.mask.feather_px if context.request.mask else 0
        output = exact_mask_composite(source, generated, effective_mask, feather_px=feather)
        return GeneratorOutput(image=output, mask=effective_mask, metadata={"opacity": opacity, "bounds": list(bounds)})


class AlphaBlendGenerator:
    def generate(self, context: GenerationContext) -> GeneratorOutput:
        asset, asset_mask, bounds = _fit_asset_to_target(context, auto_match=False)
        source = to_bgr(context.source)
        x1, y1, x2, y2 = bounds
        opacity = float(np.clip(context.request.parameters.get("opacity", 0.35 + 0.6 * context.request.severity), 0.0, 1.0))
        alpha = (asset_mask.astype(np.float32) / 255.0 * opacity)[..., None]
        region = source[y1:y2, x1:x2].astype(np.float32)
        generated = source.copy()
        generated[y1:y2, x1:x2] = np.clip(region * (1.0 - alpha) + asset.astype(np.float32) * alpha, 0, 255).astype(np.uint8)
        placed_mask = np.zeros(context.target_mask.shape, dtype=np.uint8)
        placed_mask[y1:y2, x1:x2] = asset_mask
        effective_mask = cv2.bitwise_and(placed_mask, context.target_mask)
        if not np.any(effective_mask):
            effective_mask = placed_mask
        feather = context.request.mask.feather_px if context.request.mask else 3
        output = exact_mask_composite(source, generated, effective_mask, feather_px=feather)
        return GeneratorOutput(image=output, mask=effective_mask, metadata={"opacity": opacity, "bounds": list(bounds)})


class AssetCompositeGenerator:
    def generate(self, context: GenerationContext) -> GeneratorOutput:
        asset, asset_mask, bounds = _fit_asset_to_target(context, auto_match=True)
        source = to_bgr(context.source)
        x1, y1, x2, y2 = bounds
        opacity = float(np.clip(context.request.parameters.get("opacity", 0.55 + 0.45 * context.request.severity), 0.0, 1.0))
        alpha = (asset_mask.astype(np.float32) / 255.0 * opacity)[..., None]
        region = source[y1:y2, x1:x2].astype(np.float32)
        generated = source.copy()
        generated[y1:y2, x1:x2] = np.clip(region * (1.0 - alpha) + asset.astype(np.float32) * alpha, 0, 255).astype(np.uint8)
        placed_mask = np.zeros(context.target_mask.shape, dtype=np.uint8)
        placed_mask[y1:y2, x1:x2] = asset_mask
        effective_mask = cv2.bitwise_and(placed_mask, context.target_mask)
        if not np.any(effective_mask):
            effective_mask = placed_mask
        feather = context.request.mask.feather_px if context.request.mask else 3
        output = exact_mask_composite(source, generated, effective_mask, feather_px=feather)
        return GeneratorOutput(
            image=output,
            mask=effective_mask,
            metadata={
                "opacity": opacity,
                "bounds": list(bounds),
                "color_match": float(context.request.parameters.get("color_match", 0.65)),
                "noise_match": float(context.request.parameters.get("noise_match", 0.25)),
            },
        )


class SeamlessCloneGenerator:
    def generate(self, context: GenerationContext) -> GeneratorOutput:
        asset, asset_mask, bounds = _fit_asset_to_target(context, auto_match=bool(context.request.parameters.get("auto_match", False)))
        source = to_bgr(context.source)
        x1, y1, x2, y2 = bounds
        # seamlessClone expects source/mask and destination center; use clipped asset as source.
        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        mode_name = str(context.request.parameters.get("clone_mode", "normal"))
        modes = {
            "normal": cv2.NORMAL_CLONE,
            "mixed": cv2.MIXED_CLONE,
            "monochrome": cv2.MONOCHROME_TRANSFER,
        }
        if mode_name not in modes:
            raise SyntheticValidationError("clone_mode must be normal, mixed, or monochrome")
        try:
            generated = cv2.seamlessClone(asset, source, asset_mask, center, modes[mode_name])
        except cv2.error as exc:
            raise SyntheticValidationError(
                "seamless clone failed; make the target mask larger or move it away from the image edge"
            ) from exc
        placed_mask = np.zeros(context.target_mask.shape, dtype=np.uint8)
        placed_mask[y1:y2, x1:x2] = asset_mask
        effective_mask = cv2.bitwise_and(placed_mask, context.target_mask)
        if not np.any(effective_mask):
            effective_mask = placed_mask
        feather = context.request.mask.feather_px if context.request.mask else 3
        output = exact_mask_composite(source, generated, effective_mask, feather_px=feather)
        return GeneratorOutput(image=output, mask=effective_mask, metadata={"clone_mode": mode_name, "bounds": list(bounds)})
