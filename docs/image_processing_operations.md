# Image Processing Operation Guide

이 문서는 기본 Registry에 등록된 OpenCV 기반 image processing operation의
입출력 계약과 주요 파라미터를 정리합니다. 구현 범위는
[OpenCV 4.13 Image Processing Tutorials](https://docs.opencv.org/4.13.0/d2/d96/tutorial_py_table_of_contents_imgproc.html)를
및 GUI·Feature2D·Machine Learning 튜토리얼을 기준으로 확장했습니다.

## 공통 실행 형태

Python에서는 Registry를 통해 실행합니다.

```python
result = registry.execute(
    operation="operation_name",
    inputs={"image": image_data},
    params={"parameter": value},
)

if not result.success:
    print(result.error)
```

HTTP API에서는 `multipart/form-data`의 `payload`에 JSON 문자열을 넣고 이미지
파일은 `files`로 전달합니다. `image_inputs[].file_index`는 업로드 파일 순서입니다.

## Operation 목록

| 카테고리 | Operation | 입력 조건 | 주요 출력 |
|---|---|---|---|
| Annotation | `draw_annotations` | image + annotation 목록 | 주석 BGR 이미지 |
| Adjustment | `adjust_tone` | uint8/uint16 image | tone 조정 이미지 |
| Adjustment | `adjust_color` | BGR/RGB(+alpha) uint8 | color 조정 이미지 |
| Adjustment | `apply_lut` | uint8 image + 1D LUT | LUT 이미지 |
| Adjustment | `apply_3d_lut` | RGB/BGR(+alpha) uint8 + color cube | 3D LUT 이미지 |
| Adjustment | `invert` | uint8/uint16 image | alpha 보존 반전 이미지 |
| Color | `convert_color` | uint8, 지원 색공간 | 변환 이미지 |
| Color | `color_quantization` | uint8 image | 제한 색상 BGR 이미지, centers |
| Classification | `model_predict` | ModelData + 2D features | predictions, 모델 정보 |
| Compositing | `blend_images` | 동일 규격 image 2장 | blend mode 합성 이미지 |
| Compositing | `apply_mask` | base + effect + mask | mask 합성 이미지 |
| Compositing | `image_arithmetic` | 동일 규격 image 2장 | 산술 연산 이미지 |
| Compositing | `weighted_sum` | 동일 규격 image 2장 | 가중합 이미지 |
| Compositing | `bitwise_operation` | image 1~2장 + 선택 mask | bitwise 이미지 |
| Compositing | `seamless_clone` | source + destination + mask | Poisson 합성 이미지 |
| Effects | `vignette` | uint8/uint16 image | vignette 이미지 |
| Effects | `add_grain` | uint8/uint16 image | 재현 가능한 grain 이미지 |
| Effects | `edge_preserving_filter` | BGR/RGB uint8 | 경계 보존 평활화 이미지 |
| Effects | `detail_enhance` | BGR/RGB uint8 | detail 강조 이미지 |
| Effects | `pencil_sketch` | BGR/RGB uint8 | gray/color sketch 2장 |
| Effects | `stylization` | BGR/RGB uint8 | stylized 이미지 |
| Effects | `color_change` | BGR/RGB uint8 + mask | 국소 색상 변경 이미지 |
| Effects | `illumination_change` | BGR/RGB uint8 + mask | 국소 조명 변경 이미지 |
| Effects | `texture_flattening` | BGR/RGB uint8 + mask | 국소 texture 평탄화 이미지 |
| Threshold | `global_threshold` | GRAY uint8 | mask, 실제 threshold |
| Threshold | `adaptive_threshold` | GRAY uint8 | binary mask |
| Filtering | `filter_2d` | image + 2D kernel array | convolution 이미지 |
| Filtering | `gaussian_blur` | image | 평활화 이미지 |
| Filtering | `box_blur` | image | 평활화 이미지 |
| Filtering | `median_blur` | image | 평활화 이미지 |
| Filtering | `bilateral_filter` | image | 경계 보존 평활화 이미지 |
| Morphology | `morphology` | image/mask | morphology 결과 |
| Gradient | `sobel` | GRAY uint8 | uint8 gradient |
| Gradient | `scharr` | GRAY uint8 | uint8 gradient |
| Gradient | `laplacian` | GRAY uint8 | uint8 gradient |
| Gradient | `canny` | GRAY uint8 | binary edge mask |
| Geometry | `resize` | image | 크기 변경 이미지 |
| Geometry | `rotate` | image | 회전 이미지 |
| Geometry | `flip` | image | 반전 이미지 |
| Geometry | `warp_affine` | image + 3쌍 points | affine 변환 이미지 |
| Geometry | `warp_perspective` | image + 4쌍 points | perspective 변환 이미지 |
| Histogram | `histogram` | uint8 | histogram, bin edges |
| Histogram | `equalize_histogram` | GRAY uint8 | equalization 이미지 |
| Histogram | `clahe` | GRAY uint8 | CLAHE 이미지 |
| Contour | `find_contours` | GRAY/BINARY uint8 | 주석 이미지, contour, features |
| Segmentation | `watershed` | BGR uint8 | 경계 이미지, int32 labels |
| Segmentation | `grabcut` | BGR uint8 | foreground, binary mask |
| Segmentation | `kmeans_segmentation` | image | 양자화 이미지, int32 labels, centers |
| Detection | `hough_lines_p` | GRAY/BINARY uint8 | 주석 이미지, lines |
| Detection | `hough_circles` | GRAY uint8 | 주석 이미지, circles |
| Transform | `dft_spectrum` | GRAY | magnitude spectrum |
| Transform | `image_pyramid` | image | pyrDown/pyrUp 결과 |
| Matching | `template_match` | GRAY/BGR uint8 2장 | 주석 이미지, response, best match |
| Feature | `harris_corners` | uint8 image | keypoints, response, 주석 이미지 |
| Feature | `shi_tomasi_corners` | uint8 image | keypoints, 주석 이미지 |
| Feature | `fast_keypoints` | uint8 image | keypoints, 주석 이미지 |
| Feature | `sift_features` | uint8 image | keypoints, float descriptors |
| Feature | `surf_features` | uint8 image + contrib/nonfree | keypoints, descriptors |
| Feature | `brief_descriptors` | uint8 image + contrib | keypoints, binary descriptors |
| Feature | `orb_features` | uint8 image | keypoints, binary descriptors |
| Feature | `hog_descriptor` | uint8 image | resized gray image, HOG row |
| Matching | `feature_match` | uint8 image 2장 | match 이미지, 대응점 metrics |
| Registration | `estimate_homography` | N×2 points 2개, N≥4 | 3×3 matrix, inlier mask |
| Registration | `localize_planar_object` | query + scene image | polygon, homography, metrics |

Operation의 전체 파라미터 스키마는 API 실행 후 다음 endpoint에서 조회할 수
있습니다.

```text
GET /api/v1/operations/{operation_name}
```

Adjustment, Effects, Compositing의 LUT 형식과 수식, 입력 이름, 전체 mode 목록은
[`editing_filters_and_compositing.md`](editing_filters_and_compositing.md)를
참고하세요.

## 주요 사용 예시

### Color 변환

```python
result = registry.execute(
    operation="convert_color",
    inputs={"image": bgr_image},
    params={"target_color_space": "gray"},
)
```

지원 대상은 `gray`, `bgr`, `rgb`, `hsv`, `lab`, `bgra`, `rgba`입니다.

### Otsu Threshold

```python
result = registry.execute(
    operation="global_threshold",
    inputs={"image": gray_image},
    params={
        "mode": "binary",
        "use_otsu": True,
    },
)

used_threshold = result.output.data["threshold"]
mask = result.output.images["image"]
```

Otsu는 `binary` 또는 `binary_inv` 모드에서만 사용할 수 있습니다.

### Morphology

```python
result = registry.execute(
    operation="morphology",
    inputs={"image": binary_mask},
    params={
        "operation": "close",
        "kernel_shape": "ellipse",
        "kernel_size": 5,
        "iterations": 2,
    },
)
```

`operation`은 `erode`, `dilate`, `open`, `close`, `gradient`, `tophat`,
`blackhat`을 지원합니다.

### Affine 변환

Point 입력은 `inputs`에 JSON 배열로 전달할 수 있습니다.

```python
result = registry.execute(
    operation="warp_affine",
    inputs={
        "image": image,
        "source_points": [[0, 0], [639, 0], [0, 479]],
        "destination_points": [[20, 10], [620, 30], [15, 460]],
    },
    params={"width": 640, "height": 480},
)
```

### GrabCut

```python
result = registry.execute(
    operation="grabcut",
    inputs={"image": bgr_image},
    params={
        "x": 20,
        "y": 20,
        "width": 500,
        "height": 400,
        "iterations": 5,
    },
)
```

사각형은 이미지 내부에 완전히 포함되어야 합니다.

### Template Matching

```python
result = registry.execute(
    operation="template_match",
    inputs={
        "image": source_image,
        "template": template_image,
    },
    params={"method": "ccoeff_normed"},
)

best_match = result.output.data["best_match"]
response = result.output.images["response"]
```

source와 template은 동일한 색공간과 dtype이어야 하고 template이 source보다
작아야 합니다. HTTP API에서는 두 파일을 업로드하고 각각 `image`, `template`
입력에 binding합니다.

### ORB 특징과 매칭

```python
features = registry.execute(
    operation="orb_features",
    inputs={"image": image},
)

matches = registry.execute(
    operation="feature_match",
    inputs={"image1": image, "image2": second_image},
    params={"algorithm": "orb", "matcher": "bf"},
)
```

`feature_match`는 Lowe ratio test를 적용한 뒤 거리순으로 최대 `max_matches`개를
반환합니다. SIFT는 L2, ORB는 Hamming 거리 규칙을 자동 선택합니다.

### K-Means 분할

```python
result = registry.execute(
    operation="kmeans_segmentation",
    inputs={"image": image},
    params={"clusters": 5, "random_seed": 42},
)

label_map = result.output.images["labels"]
centers = result.output.data["centers"]
```

학습 표본 수는 `sample_size`로 제한하고 전체 픽셀 배정은 chunk로 처리합니다.
색상 수만 줄일 목적이면 uint8 전용 `color_quantization`을 사용합니다.

## 성능 및 메모리 주의사항

- `resize`, `rotate(expand=True)`, `warp_*`, `image_pyramid(up)`은 결과 픽셀
  수를 실행 전에 검사합니다.
- Pipeline의 `retain_intermediates`는 디버깅 시에만 `True`로 두는 것이 좋습니다.
- `watershed.labels`와 `template_match.response`는 dtype 보존을 위해 PNG 대신
  `.npy`로 직렬화됩니다.
- 큰 이미지 또는 중간 결과가 여러 개인 요청은 `response_format=zip`을
  권장합니다.
- Contour, histogram, detection 배열은 API의 inline array 제한을 적용받습니다.
- Feature descriptor와 match 목록도 inline array 제한을 적용받습니다. 큰 결과는
  `max_features`/`max_matches`를 줄이거나 Python Registry에서 직접 처리하세요.
