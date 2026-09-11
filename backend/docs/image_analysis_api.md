# Image Analysis API

프론트엔드에서 원본 이미지와 전처리 결과를 동일한 기준으로 비교하기 위한 공통 분석 API입니다.
분석 로직은 `src/analysis/ImageAnalyzer`에 모여 있으므로 업로드 이미지, Operation 출력,
Pipeline/Recipe 최종 출력 및 필요 시 중간 출력에 동일한 계산 기준이 적용됩니다.

## 1. 제공 정보

### 기본 이미지 정보

- width / height / channels / shape
- pixel count
- dtype
- channel당 bit depth / pixel당 bit 수
- color space
- aspect ratio
- decoded memory size (`decoded_size_bytes`)
- 원본 업로드 파일 크기 (`source_size_bytes`, standalone analysis에서 제공)

전처리 결과의 PNG/NPY 인코딩 크기는 기존 실행 응답의 각 image `size_bytes`에서 확인합니다.

### Intensity 통계

컬러 이미지도 grayscale luminance 기준 통계를 함께 계산합니다.

- min / max / dynamic range
- mean / median
- standard deviation / variance
- percentile: 1, 5, 25, 50, 75, 95, 99%
- skewness
- excess kurtosis

큰 이미지의 percentile/고차 모멘트는 메모리 사용량을 제한하기 위해 균일 stride sample을
사용할 수 있습니다. `quantiles_sampled`, `sample_count`, `total_count`로 확인할 수 있습니다.
mean/std/min/max는 전체 데이터를 기준으로 계산합니다.

### Histogram

- Gray histogram: grayscale 이미지 및 컬러 이미지의 luminance
- RGB histogram: 컬러 이미지에만 제공
- HSV histogram: 컬러 이미지에만 제공
  - H: 색상 분포
  - S: 채도 분포
  - V: 밝기 분포

HSV는 전처리 선택 시 특히 S/V 분포 확인에 유용합니다. H 값은 saturation이 매우 낮은
pixel에서는 해석 가치가 낮으므로 S histogram과 함께 보는 것을 권장합니다.

`uint8`, `uint16`, `int16` histogram은 dtype 범위를 고정하여 원본/처리 결과 간 X축을
동일하게 비교할 수 있습니다. 파생 HSV 변환은 큰 이미지에서 sampling될 수 있으며
`sampled`, `sample_count`, `total_count`로 표시됩니다.

### 전처리 선택에 유용한 특징값

- entropy_bits: 밝기 분포의 정보량
- rms_contrast: grayscale 표준편차 기반 대비
- normalized_mean_intensity: 0~1 정규화 평균 밝기
- normalized_std_intensity: dtype range 대비 표준편차
- dark_pixel_ratio / bright_pixel_ratio: dtype 범위 하단/상단 1% clipping 비율
- nonzero_ratio
- laplacian_variance: focus/sharpness 지표
- tenengrad: Sobel gradient 기반 sharpness 지표
- mean_gradient_magnitude
- edge_density: adaptive Canny 기반 edge pixel 비율
- intensity center of mass X/Y
- 컬러 이미지: mean saturation, mean value, colorfulness

Laplacian/Tenengrad/edge density/colorfulness 등의 파생 특징은 매우 큰 이미지에서
`feature_max_pixels`까지 축소해 계산합니다. 결과의 `features.sampled`, `sample_width`,
`sample_height`로 확인할 수 있습니다.

## 2. X/Y Projection Profile

프로파일은 grayscale 값을 기준으로 계산합니다.

- X profile: 각 X(column)에 대해 Y 방향 pixel을 합산
- Y profile: 각 Y(row)에 대해 X 방향 pixel을 합산
- `sum_profile`: 축 누적합(projection sum)
- `mean_profile`: 이미지 크기에 덜 민감한 평균 intensity profile
- `derivative_profile`: smoothing 적용 후 `sum_profile`의 1차 수치 미분

프론트엔드 차트에는 일반적으로 `mean_profile`과 `derivative_profile`을 함께 표시하는 것이
가독성이 좋습니다. 원본 누적합 값 자체가 필요하면 `sum_profile`을 사용합니다.

폭/높이가 매우 큰 이미지는 `profile_max_points`를 넘으면 block average로 downsampling합니다.
`positions`는 원본 이미지의 pixel 좌표를 유지하므로 그래프 X축 좌표로 그대로 사용할 수 있습니다.

## 3. Standalone 이미지 분석

`POST /api/v1/analysis/image`

multipart form:

- `file`: 분석할 이미지
- `payload`: `ImageAnalysisPayload` JSON string

예시:

```json
{
  "name": "sem_sample_001",
  "options": {
    "histogram_bins": 256,
    "include_gray_histogram": true,
    "include_rgb_histogram": true,
    "include_hsv_histogram": true,
    "include_features": true,
    "include_profiles": true,
    "include_profile_derivative": true,
    "profile_max_points": 4096,
    "profile_smoothing_window": 3
  }
}
```

## 4. Operation 결과 분석

기존 Operation payload에 `analysis`를 추가하면 됩니다.

```json
{
  "image_inputs": [
    {"input_name": "image", "file_index": 0}
  ],
  "params": {
    "kernel_size": 5
  },
  "analysis": {
    "include_profiles": true,
    "profile_smoothing_window": 3
  }
}
```

응답의 각 output image metadata 아래에 다음과 같이 추가됩니다.

```text
output.images.<output_name>.analysis
```

`analysis`를 전달하지 않으면 기존 응답과 동일하며 분석 계산 비용도 발생하지 않습니다.

## 5. Pipeline / Recipe 결과 분석

```json
{
  "image_inputs": [
    {"input_name": "image", "file_index": 0}
  ],
  "retain_intermediates": true,
  "analysis": {
    "include_profiles": true
  },
  "analyze_intermediates": false
}
```

- 최종 output: `analysis`가 있으면 분석 결과 포함
- intermediates: `analyze_intermediates=true`인 경우에만 분석 결과 포함

프론트엔드 초기 화면에서는 다음 설정을 권장합니다.

```json
{
  "retain_intermediates": true,
  "analysis": {
    "include_profiles": true,
    "profile_max_points": 2048
  },
  "analyze_intermediates": false
}
```

사용자가 특정 중간 step을 상세 선택했을 때만 중간 분석을 요청하면 반응성을 유지하기 쉽습니다.

## 6. 프론트엔드 권장 구성

```text
[Before Image]                         [After Image]

Basic Info                             Basic Info
Histogram                              Histogram
Statistics                             Statistics
Features                               Features
X/Y Profile                            X/Y Profile
```

Histogram은 탭 구조가 적합합니다.

```text
[Gray] [RGB] [HSV]
```

Grayscale/SEM 이미지에서는 RGB/HSV 탭을 숨기고 Gray만 노출합니다.

특징값은 처음부터 전부 크게 표시하기보다 다음 6개를 summary card로 우선 표시하는 것을 권장합니다.

```text
Mean Brightness | Contrast | Entropy | Sharpness(Laplacian) | Edge Density | Clipping
```

나머지 percentile, skewness, kurtosis, Tenengrad 등은 상세 패널에서 확인하도록 구성하면 화면이
복잡해지지 않습니다.
