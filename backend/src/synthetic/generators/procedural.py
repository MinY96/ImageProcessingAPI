from __future__ import annotations

import cv2
import numpy as np

from ..common import exact_mask_composite, parse_color, to_bgr
from ..schemas import ProceduralPattern
from .base import GenerationContext, GeneratorOutput


class ProceduralGenerator:
    def generate(self, context: GenerationContext) -> GeneratorOutput:
        rng = np.random.default_rng(context.seed)
        source = to_bgr(context.source)
        params = context.request.parameters
        pattern = ProceduralPattern(str(params.get("pattern", ProceduralPattern.BLOB.value)))
        severity = context.request.severity
        mask = context.target_mask
        generated = source.copy()

        default_color = (35, 35, 35)
        if pattern in {ProceduralPattern.DROPLET, ProceduralPattern.POOLING}:
            default_color = (170, 175, 180)
        color = np.asarray(parse_color(params.get("color"), default=default_color), dtype=np.float32)
        opacity = float(np.clip(params.get("opacity", 0.25 + 0.65 * severity), 0.0, 1.0))

        if pattern == ProceduralPattern.CRACK:
            layer = np.zeros_like(source)
            layer[:] = color.astype(np.uint8)
            alpha = (mask.astype(np.float32) / 255.0 * opacity)[..., None]
            generated = np.rint(source * (1.0 - alpha) + layer * alpha).astype(np.uint8)

        elif pattern in {ProceduralPattern.DROPLET, ProceduralPattern.POOLING}:
            layer = source.astype(np.float32)
            alpha = (mask.astype(np.float32) / 255.0)[..., None]
            tint = np.broadcast_to(color, source.shape)
            base = layer * (1.0 - opacity * alpha) + tint * (opacity * alpha)
            highlight = cv2.GaussianBlur(mask, (0, 0), max(1.0, 2.0 + severity * 6.0)).astype(np.float32) / 255.0
            gx = cv2.Sobel(highlight, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(highlight, cv2.CV_32F, 0, 1, ksize=3)
            rim = np.clip(np.sqrt(gx * gx + gy * gy) * (2.0 + severity * 6.0), 0.0, 1.0)[..., None]
            base += rim * (35.0 + 80.0 * severity)
            generated = np.clip(base, 0, 255).astype(np.uint8)

        elif pattern == ProceduralPattern.SPECK:
            layer = source.copy().astype(np.float32)
            ys, xs = np.where(mask > 0)
            count = max(10, int(len(xs) * (0.01 + severity * 0.08)))
            if len(xs):
                indices = rng.integers(0, len(xs), size=count)
                for idx in indices:
                    radius = int(rng.integers(1, max(2, int(2 + severity * 8))))
                    cv2.circle(layer, (int(xs[idx]), int(ys[idx])), radius, tuple(float(x) for x in color), -1, cv2.LINE_AA)
            generated = np.clip(layer, 0, 255).astype(np.uint8)

        elif pattern == ProceduralPattern.TEXTURE:
            noise = rng.normal(0.0, 12.0 + 45.0 * severity, size=source.shape).astype(np.float32)
            textured = np.clip(source.astype(np.float32) + noise, 0, 255)
            alpha = (mask.astype(np.float32) / 255.0 * opacity)[..., None]
            generated = np.rint(source * (1.0 - alpha) + textured * alpha).astype(np.uint8)

        else:  # blob / stain
            layer = np.broadcast_to(color, source.shape).astype(np.float32)
            alpha = cv2.GaussianBlur(mask, (0, 0), max(0.5, 1.0 + severity * 4.0)).astype(np.float32)
            alpha = (alpha / 255.0 * opacity)[..., None]
            generated = np.rint(source * (1.0 - alpha) + layer * alpha).astype(np.uint8)

        feather = context.request.mask.feather_px if context.request.mask else 3
        output = exact_mask_composite(source, generated, mask, feather_px=feather)
        return GeneratorOutput(
            image=output,
            mask=mask,
            metadata={"pattern": pattern.value, "opacity": opacity},
        )
