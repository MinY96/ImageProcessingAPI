# Editing Filters and Compositing

사진 편집과 이미지 간 연산을 Registry/Pipeline/API에서 동일한 계약으로 사용하기
위한 안내입니다. 기본 Registry에는 이 문서의 20개 operation이 자동 등록됩니다.

## 목록

| 분류 | Operation | 핵심 기능 |
|---|---|---|
| Adjustment | `adjust_tone` | exposure(EV), contrast, brightness, gamma |
| Adjustment | `adjust_color` | hue, saturation, vibrance, temperature, tint |
| Adjustment | `apply_lut` | 256-entry 공통/채널별 1D LUT |
| Adjustment | `apply_3d_lut` | nearest 또는 trilinear RGB color cube |
| Adjustment | `invert` | 색상 채널 반전, alpha 보존 |
| Compositing | `blend_images` | normal, multiply, screen, overlay, soft/hard light, difference, add, subtract |
| Compositing | `apply_mask` | mask로 base/effect 혼합 |
| Compositing | `image_arithmetic` | add, subtract, absdiff, multiply, divide, min, max |
| Compositing | `weighted_sum` | `alpha*A + beta*B + gamma` |
| Compositing | `bitwise_operation` | AND, OR, XOR, NOT, NAND, NOR, XNOR과 선택 mask |
| Effects | `vignette` | 위치·반경·softness를 갖는 radial 감광 |
| Effects | `add_grain` | Gaussian/Uniform, mono/color, seed 기반 film grain |
| Effects | `edge_preserving_filter` | OpenCV Photo edge-preserving smoothing |
| Effects | `detail_enhance` | OpenCV Photo detail enhancement |
| Effects | `pencil_sketch` | gray와 color sketch 동시 출력 |
| Effects | `stylization` | OpenCV Photo stylization |
| Effects | `color_change` | mask 내부 local color change |
| Effects | `illumination_change` | mask 내부 local illumination change |
| Effects | `texture_flattening` | mask 내부 edge-preserving texture flattening |
| Compositing | `seamless_clone` | normal/mixed/monochrome Poisson cloning |

## LUT 계약

`apply_lut`의 `lut` 입력은 `(256,)` 또는 `(256, image_channels)` 배열입니다.
값은 `[0, 255]`로 clip되며 `intensity`로 원본과 혼합합니다. 4채널 이미지의 alpha는
LUT 대상에서 제외됩니다.

`apply_3d_lut`의 `lut` 입력은 `(N, N, N, 3)`, `2 <= N <= 65`이고 축은
`[red, green, blue]` 순서입니다. 값 범위는 `[0, 1]` 또는 `[0, 255]`를 받습니다.
처리는 내부 RGB 표현에서 이뤄지므로 BGR 입력도 같은 cube를 재사용할 수 있고,
BGRA/RGBA의 alpha는 그대로 유지합니다. Trilinear 보간은 큰 중간 배열을 피하도록
pixel chunk 단위로 실행합니다.

```python
axis = np.linspace(0.0, 1.0, 17, dtype=np.float32)
r, g, b = np.meshgrid(axis, axis, axis, indexing="ij")
identity_cube = np.stack([r, g, b], axis=-1)

result = registry.execute(
    operation="apply_3d_lut",
    inputs={"image": image, "lut": identity_cube},
    params={"interpolation": "trilinear", "intensity": 1.0},
)
```

## 합성 및 기본 연산 계약

두 이미지를 받는 연산은 shape, dtype, color space가 모두 같아야 합니다.
`apply_mask`의 mask는 이미지와 폭·높이가 같아야 하고 uint8 또는 uint16 밝기를
`[0, 1]` weight로 해석합니다.

`image_arithmetic`은 정규화된 float32에서 계산한 뒤 포화 변환합니다. 따라서
`subtract`는 음수를 0으로 clip하고, 부호 없는 차이가 필요하면
`absolute_difference`를 사용합니다. `weighted_sum.gamma`와 arithmetic의 `offset`은
정규화 단위이므로 `gamma=0.1`은 uint8에서 약 25.5를 더합니다.

`bitwise_operation`에서 `not`만 `image2`가 선택 사항입니다. `nand`, `nor`,
`xnor`는 각각 `NOT(AND)`, `NOT(OR)`, `NOT(XOR)`로 정의했습니다. 선택 mask 바깥의
출력은 0입니다.

```python
result = registry.execute(
    operation="blend_images",
    inputs={"base": background, "layer": foreground},
    params={"mode": "overlay", "opacity": 0.65},
)
```

## OpenCV Photo 계열

Photo operation은 OpenCV 함수의 요구사항에 맞춰 BGR/RGB uint8 입력을 받고 BGR로
출력합니다. `color_change`, `illumination_change`, `texture_flattening`의 mask는
source 크기의 GRAY/BINARY uint8이어야 합니다.

`seamless_clone`은 source 크기의 mask와 별도의 destination을 받습니다. `center_x`,
`center_y`는 destination 좌표이며 source/mask 영역이 해당 중심을 기준으로
destination 안에 들어가야 합니다.

```python
result = registry.execute(
    operation="seamless_clone",
    inputs={
        "source": source,
        "destination": destination,
        "mask": source_mask,
    },
    params={"center_x": 640, "center_y": 360, "mode": "mixed"},
)
```

## Pipeline 예시

```python
PipelineStepSpec(
    id="tone",
    operation="adjust_tone",
    inputs={"image": pipeline_input("image")},
    params={"contrast": 0.9, "brightness": 0.04},
)
PipelineStepSpec(
    id="vignette",
    operation="vignette",
    inputs={"image": step_output("tone")},
    params={"strength": 0.35},
)
PipelineStepSpec(
    id="grain",
    operation="add_grain",
    inputs={"image": step_output("vignette")},
    params={"amount": 0.03, "random_seed": 11},
)
```

## 성능과 재현성

- 3D LUT는 100,000 pixel chunk로 보간합니다.
- OpenCV Photo 함수는 입력당 1,600만 pixel, 합성 계열은 연산별 pixel budget을
  검사합니다.
- `add_grain`은 `random_seed`가 같으면 동일 결과를 만듭니다. `grain_size > 1`이면
  저해상도 noise를 생성한 뒤 최근접 보간하므로 메모리와 생성 비용도 줄어듭니다.
- 편집 과정 확인이 필요할 때만 Pipeline의 `retain_intermediates=True`를 사용합니다.

각 operation의 authoritative parameter schema는
`GET /api/v1/operations/{operation_name}`에서 조회할 수 있습니다.
