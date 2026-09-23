# Synthetic NG Generator API

정상 이미지에 국소적인 Synthetic anomaly를 생성하기 위한 독립 백엔드 모듈입니다.
기존 `Operation/Pipeline/Workflow`와 분리되어 있으며, 결과는 `image + defect mask + difference + metadata`로 반환됩니다.

## 지원 방식

| method | 용도 | Asset 필요 |
|---|---|---|
| `procedural` | blob/stain/droplet/pooling/crack/speck/texture | 아니오 |
| `cut_paste` | 원본/Asset patch 복사 | 선택 |
| `alpha_blend` | 투명도 기반 defect 합성 | 예 |
| `seamless_clone` | OpenCV Poisson seamless clone | 예 |
| `asset_composite` | 색/노이즈/blur matching 포함 Asset 합성 | 예 |
| `diffusion_inpaint` | SDXL / FLUX / OpenVINO SD1.5 로컬 inpainting | 아니오 |

## 저장 위치

기본값:

```text
.image_processing_data/
├── synthetic/assets/
└── models/diffusion/
```

`ApiSettings`에서 변경할 수 있습니다.

## Mask 종류

`manual`, `rectangle`, `ellipse`, `polygon`, `random_blob`, `perlin`, `crack`

모든 좌표/크기 비율은 0~1 normalized 값을 사용하므로 프론트엔드 canvas 해상도와 실제 이미지 해상도를 분리할 수 있습니다.
`manual`은 `target_mask` 파일을 업로드해야 합니다.

## 주요 API

```text
GET    /api/v1/synthetic/methods
GET    /api/v1/synthetic/diffusion/models
GET    /api/v1/synthetic/diffusion/prompt-presets
POST   /api/v1/synthetic/diffusion/unload

GET    /api/v1/synthetic/assets
POST   /api/v1/synthetic/assets
GET    /api/v1/synthetic/assets/{asset_id}
GET    /api/v1/synthetic/assets/{asset_id}/image
GET    /api/v1/synthetic/assets/{asset_id}/mask
DELETE /api/v1/synthetic/assets/{asset_id}

POST   /api/v1/synthetic/generate
```

## Procedural 예시

`multipart/form-data`

- `payload`: JSON string
- `source_image`: 원본 이미지
- `target_mask`: 선택
- `asset_image`: 선택
- `asset_mask`: 선택

```json
{
  "method": "procedural",
  "defect_type": "liquid_pool",
  "severity": 0.6,
  "count": 4,
  "seed": 100,
  "mask": {
    "type": "ellipse",
    "center_x": 0.55,
    "center_y": 0.45,
    "width_ratio": 0.18,
    "height_ratio": 0.12,
    "feather_px": 4
  },
  "parameters": {
    "pattern": "pooling",
    "opacity": 0.5
  }
}
```

`count=4`이면 seed `100, 101, 102, 103`을 사용해 4개 candidate를 생성합니다.

## Asset Library 예시

Asset은 `image.png`, 선택적인 `mask.png`, `metadata.json`으로 저장됩니다.
Photo hose의 droplet/pooling, Wet bath의 wafer fragment/metal part 등을 category로 관리할 수 있습니다.

```json
{
  "asset_id": "wet_broken_wafer_001",
  "name": "Broken wafer 001",
  "category": "broken_wafer",
  "tags": ["wet", "wafer_fragment"]
}
```

Asset 생성 후 `asset_id`를 합성 요청에 전달하면 됩니다.

## Diffusion Inpainting

Diffusion은 선택 의존성입니다. 기본 OpenCV 서버는 `diffusers`가 없어도 기동합니다.

```bash
pip install -r requirements-diffusion.txt
```

기본 설정은 `synthetic_diffusion_local_files_only=True`입니다. 따라서 사내망/오프라인 환경에서는 모델을 미리 캐시에 준비하거나 `ApiSettings`에서 다운로드 허용 형태로 실행해야 합니다.

지원 provider:

- `sdxl_inpaint`: `diffusers/stable-diffusion-xl-1.0-inpainting-0.1`
- `flux_fill`: `black-forest-labs/FLUX.1-Fill-dev` (experimental, CPU offload 기본)
- `sd15_openvino_inpaint`: `stable-diffusion-v1-5/stable-diffusion-inpainting`를 OpenVINO IR로 변환해 Intel CPU/iGPU에서 실행

### OpenVINO SD1.5 Inpainting

사무용 Intel PC에서 512x512 ROI 단위로 Synthetic NG를 생성하기 위한 provider입니다.
기본 OpenVINO 장치는 `AUTO`이며 `ApiSettings.synthetic_openvino_device`에서 `CPU`, `GPU`, `GPU.0` 등으로 변경할 수 있습니다.

선택 의존성 설치:

```bash
pip install -r requirements-openvino-diffusion.txt
```

또는 최신 Optimum Intel 권장 방식:

```bash
pip install --upgrade --upgrade-strategy eager "optimum-intel[openvino]"
```

최초 1회 모델 다운로드 + OpenVINO IR 변환:

```bash
python scripts/prepare_openvino_sd15_inpaint.py --device CPU --compile-test
```

Intel GPU 드라이버가 OpenVINO에 정상 노출된다면:

```bash
python scripts/prepare_openvino_sd15_inpaint.py --device GPU --compile-test
```

API 서버에서 `synthetic_diffusion_local_files_only=True`를 유지하면, 이후에는 저장된 OpenVINO 모델만 사용하므로 외부 다운로드를 시도하지 않습니다.
모델은 기본적으로 아래에 저장됩니다.

```text
.image_processing_data/models/diffusion/
└── sd15_openvino_inpaint/
    └── exported/
        └── stable-diffusion-v1-5__stable-diffusion-inpainting_512x512/
```

OpenVINO 요청 예시:

```json
{
  "method": "diffusion_inpaint",
  "defect_type": "tear_with_seepage",
  "count": 1,
  "seed": 100,
  "mask": {
    "type": "ellipse",
    "center_x": 0.52,
    "center_y": 0.50,
    "width_ratio": 0.14,
    "height_ratio": 0.10,
    "rotation_deg": 15,
    "feather_px": 5
  },
  "parameters": {
    "model": "sd15_openvino_inpaint",
    "prompt_preset": "tear_with_seepage",
    "device": "AUTO",
    "input_size": 512,
    "steps": 20,
    "guidance_scale": 7.0,
    "strength": 0.85
  }
}
```

`prompt`를 직접 넘기면 `prompt_preset`보다 우선합니다. `negative_prompt`도 직접 지정할 수 있으며, 생략하면 preset의 공통 negative prompt를 사용합니다.

호스 누수 preset은 다음 10개를 제공합니다.

- `micro_seepage`
- `small_joint_leak`
- `small_pooling`
- `hairline_tear`
- `tear_with_seepage`
- `tear_with_pooling`
- `forming_droplet`
- `downward_drip`
- `wet_halo`
- `small_pressure_leak`

`GET /api/v1/synthetic/diffusion/prompt-presets`로 실제 prompt/negative prompt 전체를 조회할 수 있습니다.

요청 예시:

```json
{
  "method": "diffusion_inpaint",
  "defect_type": "broken_wafer",
  "count": 4,
  "seed": 1234,
  "mask": {
    "type": "polygon",
    "polygon": [[0.42, 0.51], [0.48, 0.48], [0.51, 0.56], [0.45, 0.59]],
    "feather_px": 5
  },
  "parameters": {
    "model": "sdxl_inpaint",
    "prompt": "a small broken silicon wafer fragment inside an industrial semiconductor wet bath, realistic CCTV image, same lighting and perspective",
    "negative_prompt": "change background, change equipment, text, extra objects",
    "steps": 25,
    "guidance_scale": 7.0,
    "strength": 0.95
  }
}
```

Diffusion 출력은 최종 단계에서 원본과 다시 합성합니다. **Mask 외부 픽셀은 원본으로 복원**되므로 생성 모델이 주변 장비나 배경을 임의로 바꾸는 것을 막습니다.

## 응답

기본 `response_format=json`은 후보마다 아래 3개 PNG를 base64로 반환합니다.

- `image`: 최종 Synthetic NG
- `mask`: 실제 defect 영역
- `difference`: 원본과 절대차

`response_format=zip`을 사용하면 다음 구조로 다운로드됩니다.

```text
manifest.json
candidates/
└── 00/
    ├── image.png
    ├── mask.png
    └── difference.png
```

각 후보에는 다음 quality metric이 포함됩니다.

- `changed_area_ratio`
- `outside_mask_mean_abs_diff`
- `outside_mask_max_abs_diff`
- `inside_mask_mean_abs_diff`

`outside_mask_*` 값은 생성 결과가 지정한 defect 영역 밖의 원본을 훼손했는지 확인하기 위한 지표입니다.

## 권장 사용 순서

1. Procedural로 crack/droplet/stain baseline 생성
2. 실제/수작업 Asset을 Asset Library에 등록
3. `asset_composite`와 `seamless_clone` 비교
4. SDXL Inpainting으로 동일 mask에 candidate 4~8개 생성
5. `difference`와 outside-mask metric으로 합성 품질 확인
6. 최종 선택 이미지를 TestDataset NG로 등록해 EvaluationEngine에서 Recipe 성능 평가
