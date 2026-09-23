# OpenVINO SD 1.5 Inpainting Update

Base: `ImageProcessingAPI-main.zip` → `backend`

## Added

- `sd15_openvino_inpaint` diffusion provider
- Intel OpenVINO device selection: `AUTO`, `CPU`, `GPU`, `GPU.0`, ...
- 512x512 Stable Diffusion 1.5 Inpainting ROI workflow
- Hose leak / tear prompt presets
- `GET /api/v1/synthetic/diffusion/prompt-presets`
- model preparation / compile-test script
- OpenVINO usage example

## Install

```bash
python -m pip install -r requirements-openvino-diffusion.txt
```

The compatible stack intentionally pins `diffusers==0.39.0` because
`optimum-intel==2.2.0` requires `huggingface-hub<1.22`, while diffusers 0.40.0
requires a newer incompatible hub release.

## Prepare once

```bash
python scripts/prepare_openvino_sd15_inpaint.py --device CPU --compile-test
python scripts/prepare_openvino_sd15_inpaint.py --device GPU --compile-test
```

If the exported OpenVINO IR already exists, the second command reuses it and
only loads/compiles it for the selected device. Use `--force-export` only when
you intentionally want to recreate the IR.

## Server

```bash
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

## Validation

- Python compile check: passed
- FastAPI app import: passed
- Tests: 181 / 181 passed

The latest baseline contained Evaluation Job Queue files/tests whose schemas
and engine interface were partially disconnected. Their internal contracts
were restored without changing the current synchronous Evaluation API.
