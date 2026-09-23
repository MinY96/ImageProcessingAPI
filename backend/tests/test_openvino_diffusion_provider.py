from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PIL import Image

from src.synthetic.diffusion.openvino_sd15 import OpenVINOSD15InpaintProvider
from src.synthetic.diffusion.prompts import list_prompt_presets, resolve_prompt_preset


def test_hose_prompt_presets_are_available():
    keys = {item.key for item in list_prompt_presets()}
    assert "tear_with_seepage" in keys
    assert "small_pooling" in keys
    assert "downward_drip" in keys
    assert "localized defect" in resolve_prompt_preset("tear_with_seepage").prompt


def test_openvino_provider_resizes_to_working_size_and_back(tmp_path, monkeypatch):
    provider = OpenVINOSD15InpaintProvider(
        cache_dir=tmp_path,
        local_files_only=True,
        device="AUTO",
    )

    calls: dict = {}

    class FakePipe:
        def __call__(self, **kwargs):
            calls.update(kwargs)
            assert kwargs["image"].size == (512, 512)
            assert kwargs["mask_image"].size == (512, 512)
            generated = np.full((512, 512, 3), 210, dtype=np.uint8)
            return SimpleNamespace(images=[Image.fromarray(generated)])

    monkeypatch.setattr(provider, "_resolve_device", lambda _requested: "CPU")
    monkeypatch.setattr(provider, "_load", lambda **_kwargs: FakePipe())

    image = np.full((300, 500, 3), 100, dtype=np.uint8)
    mask = np.zeros((300, 500), dtype=np.uint8)
    mask[100:180, 220:320] = 255

    result = provider.generate(
        image_bgr=image,
        mask=mask,
        prompt="localized clear liquid leak",
        negative_prompt="background change",
        seed=123,
        parameters={"input_size": 512, "steps": 12, "guidance_scale": 6.5, "strength": 0.8},
    )

    assert result.shape == image.shape
    assert calls["num_inference_steps"] == 12
    assert calls["guidance_scale"] == 6.5
    assert calls["strength"] == 0.8
    assert calls["height"] == 512
    assert calls["width"] == 512
    assert calls["negative_prompt"] == "background change"
