# OpenCV GUI · Feature2D · Machine Learning 확장

이 문서는 OpenCV 4.13 Python 튜토리얼의 세 목차를 현재 프로젝트 구조에
배치한 결과를 정리합니다.

- [GUI Features](https://docs.opencv.org/4.13.0/dc/d4d/tutorial_py_table_of_contents_gui.html)
- [Feature Detection and Description](https://docs.opencv.org/4.13.0/db/d27/tutorial_py_table_of_contents_feature2d.html)
- [Machine Learning](https://docs.opencv.org/4.13.0/d6/de2/tutorial_py_table_of_contents_ml.html)

## 구조 원칙

서버에서 재현 가능한 순수 연산은 `OperationRegistry`에 등록합니다. 파일이나
카메라를 여는 기능은 `media_io`, 창·마우스·트랙바처럼 사용자 세션이 필요한
기능은 `ui`, 학습된 객체의 생명주기는 `machine_learning`에서 담당합니다.

| 계층 | 역할 | API/Pipeline |
|---|---|---|
| `src/image_processing` | 입력에서 출력이 결정되는 이미지·특징 연산 | 조회 및 실행 가능 |
| `src/machine_learning` | 학습, 모델 메타데이터, 모델 Registry | Python에서 모델 준비 후 추론 operation에 연결 |
| `src/media_io` | 이미지/비디오 읽기·쓰기 | 서버 endpoint 밖의 경계 계층 |
| `src/ui` | HighGUI 표시, 마우스, trackbar | 로컬 데스크톱 전용 |

## GUI 기능

| OpenCV 주제 | 프로젝트 위치 | 제공 기능 |
|---|---|---|
| 이미지 읽기/저장 | `src.media_io` | `read_image`, `write_image` |
| 이미지 표시 | `src.ui` | `show_image` |
| 비디오/카메라 읽기 | `src.media_io` | `iter_video_frames` |
| 비디오 저장 | `src.media_io` | `write_video` |
| 비디오 재생 | `src.ui` | `play_video` |
| 도형과 텍스트 그리기 | Annotation operation | `draw_annotations` |
| 마우스 그리기/ROI | `src.ui` | `paint_image`, `select_rectangle` |
| Trackbar 색상 조정 | `src.ui` | `color_palette` |

`src.ui` 함수는 DISPLAY/WAYLAND가 없는 환경에서 창을 열지 않고 명확한
`RuntimeError`를 발생시킵니다. 서버에서는 주석을 JSON 입력으로 전달하는
`draw_annotations`를 사용합니다.

```python
result = registry.execute(
    operation="draw_annotations",
    inputs={
        "image": image,
        "annotations": [
            {
                "type": "rectangle",
                "top_left": [20, 30],
                "bottom_right": [180, 140],
                "color": [0, 255, 0],
                "thickness": 2,
            },
            {
                "type": "text",
                "text": "object",
                "origin": [20, 25],
            },
        ],
    },
)
```

지원 annotation type은 `line`, `rectangle`, `circle`, `ellipse`,
`polyline`, `text`입니다.

## Feature2D

| OpenCV 주제 | Operation | 주요 출력 |
|---|---|---|
| Harris Corner | `harris_corners` | 주석 이미지, response, keypoints |
| Shi-Tomasi | `shi_tomasi_corners` | 주석 이미지, keypoints |
| FAST | `fast_keypoints` | 주석 이미지, keypoints |
| SIFT | `sift_features` | keypoints, float32 descriptors |
| SURF | `surf_features` | keypoints, descriptors |
| BRIEF | `brief_descriptors` | FAST keypoints, binary descriptors |
| ORB | `orb_features` | keypoints, binary descriptors |
| BF/FLANN Matching | `feature_match` | 대응점 목록, match 이미지 |
| Homography | `estimate_homography` | 3×3 행렬, inlier mask |
| Object Localization | `localize_planar_object` | polygon, homography, inlier metrics |

SIFT와 ORB는 기본 패키지에서 동작합니다. SURF는 contrib와 nonfree 지원이 모두
필요하고 BRIEF는 contrib가 필요합니다. 런타임에 factory 존재 여부를 검사하므로
지원되지 않는 빌드에서도 애플리케이션 시작과 operation 목록 조회는 정상입니다.

Feature matching은 `orb`/`sift`, `bf`/`flann` 조합과 Lowe ratio filtering을
지원합니다. Homography는 최소 4쌍의 점을 요구하며 `direct`, `ransac`, `lmeds`
방식을 제공합니다.

```python
result = registry.execute(
    operation="feature_match",
    inputs={"image1": first, "image2": second},
    params={"algorithm": "sift", "matcher": "flann"},
)
```

## Machine Learning

| OpenCV 주제 | 프로젝트 구성 | 설명 |
|---|---|---|
| kNN | `train_knn` + `model_predict` | 분류 학습과 추론 |
| SVM | `train_svm` + `model_predict` | C-SVC 분류, linear/RBF/poly/sigmoid |
| K-Means clustering | `kmeans_segmentation` | gray/color 픽셀 군집화와 label map |
| K-Means color quantization | `color_quantization` | 제한된 palette의 BGR uint8 이미지 |
| Digit용 특징 예 | `hog_descriptor` | 분류기에 연결 가능한 HOG feature row |
| 모델 생명주기 | `ModelRegistry` | ID와 semantic version으로 thread-safe 보관 |

학습 모델은 직렬화할 수 없는 OpenCV 런타임 객체를 포함하므로 요청 본문에 직접
넣지 않습니다. 애플리케이션 시작 시 `create_app(models=[...])`로 등록하고,
HTTP 요청에서는 `model_inputs`의 ID와 version으로 안전하게 참조합니다.

```python
from src.machine_learning import ModelRegistry, train_knn

model = train_knn(
    features,
    labels,
    model_id="digit_knn",
    version="1.0.0",
    feature_schema="hog-64x128-v1",
    default_k=5,
)

models = ModelRegistry()
models.register(model)

result = registry.execute(
    operation="model_predict",
    inputs={"model": model, "features": query_features},
)
```

K-Means는 최대 100만 개 학습 표본만 사용하고 전체 픽셀 배정은 chunk 단위로
수행합니다. 고해상도 영상에서 전체 `N × K × D` 거리 행렬을 한 번에 만들지
않아 메모리 급증을 제한하며, `random_seed`로 반복 실행을 재현할 수 있습니다.

## Registry, API, Pipeline 연결

새로운 이미지 operation은 모두 `create_default_registry()`에 포함되므로 아래
endpoint에서 기존 operation과 동일하게 조회됩니다.

```text
GET /api/v1/operations
GET /api/v1/operations/{operation_name}
POST /api/v1/operations/{operation_name}/execute
GET /api/v1/models
GET /api/v1/models/{model_id}/{version}
```

이미지, array, points 출력은 Pipeline step output으로 후속 operation에 연결할
수 있습니다. `ModelData`는 Python Pipeline 입력으로 직접 전달하거나 HTTP의
`model_inputs` binding으로 연결할 수 있습니다. HighGUI와 파일 I/O는 실행
환경에 의존하므로 Registry에 등록하지 않습니다.

```json
{
  "inputs": {"features": [[0.2, 0.1], [8.4, 8.2]]},
  "model_inputs": [
    {
      "input_name": "model",
      "model_id": "digit_knn",
      "version": "1.0.0"
    }
  ],
  "params": {"knn_k": 5}
}
```
