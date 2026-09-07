# Image Processing API Project

OpenCV 기반 이미지 처리 기능을 공통 스키마, 검증기, Registry 및 API로
확장하기 위한 프로젝트입니다.

## 현재 완료 범위

### 1. 공통 스키마

- 이미지 데이터와 이미지 제약: `ImageData`, `ImageConstraint`
- 입력/출력 슬롯과 연산 정의: `InputSlotSpec`, `OutputSlotSpec`,
  `OperationSpec`
- 실행 요청/결과: `ExecutionRequest`, `ValidatedExecutionRequest`,
  `ExecutionResult`
- 연속형, 이산형, 범주형 파라미터 스키마

### 2. 개별 파라미터 검증

- 타입, 범위, step, category choice 검증
- 필수값 및 기본값 처리
- 알 수 없는 파라미터 탐지
- 한 요청의 여러 오류를 모아서 반환

### 3. 교차 파라미터 검증

- `less_than`, `less_than_equal`
- `greater_than`, `greater_than_equal`
- `require_together`, `mutually_exclusive`
- `exactly_one_group`, `conditional_required`
- 사용자가 명시한 값(`provided_params`)과 기본값까지 적용한 최종 값
  (`params`)을 분리
- `OperationSpec` 생성 시 제약이 존재하지 않는 파라미터를 참조하는지 검증

### 4. Operation Registry

- `OperationSpec`과 실제 handler 등록
- 중복 등록 방지, 조회, 목록, 해제 및 decorator 등록
- 다중 API 요청을 고려한 thread-safe 등록/조회
- 입력 → 파라미터 → 교차 파라미터 → handler → 출력 계약 검증
- 모든 실행 결과를 `ExecutionResult`로 통일
- 원본 `OperationSpec` 변경의 영향을 받지 않도록 defensive copy 사용
- 크기 증가 operation의 최대 픽셀 수를 실행 전에 검사하여 과도한 메모리 할당 차단

OpenCV 4.13의 Image Processing, GUI, Feature2D, Machine Learning 튜토리얼을
기준 기능에 사진 편집·합성·OpenCV Photo 연산을 더해 기본 Registry에
64개 operation을 등록했습니다.

| 카테고리 | Operation |
|---|---|
| Annotation | `draw_annotations` |
| Adjustment | `adjust_tone`, `adjust_color`, `apply_lut`, `apply_3d_lut`, `invert` |
| Color | `convert_color`, `color_quantization` |
| Classification | `model_predict` |
| Compositing | `blend_images`, `apply_mask`, `image_arithmetic`, `weighted_sum`, `bitwise_operation`, `seamless_clone` |
| Effects | `vignette`, `add_grain`, `edge_preserving_filter`, `detail_enhance`, `pencil_sketch`, `stylization`, `color_change`, `illumination_change`, `texture_flattening` |
| Threshold | `global_threshold`, `adaptive_threshold` |
| Filtering | `filter_2d`, `gaussian_blur`, `box_blur`, `median_blur`, `bilateral_filter` |
| Morphology | `morphology` |
| Gradient | `sobel`, `scharr`, `laplacian`, `canny` |
| Geometry | `resize`, `rotate`, `flip`, `warp_affine`, `warp_perspective` |
| Histogram | `histogram`, `equalize_histogram`, `clahe` |
| Contour | `find_contours` |
| Segmentation | `watershed`, `grabcut`, `kmeans_segmentation` |
| Detection | `hough_lines_p`, `hough_circles` |
| Transform | `dft_spectrum`, `image_pyramid` |
| Feature | `harris_corners`, `shi_tomasi_corners`, `fast_keypoints`, `sift_features`, `surf_features`, `brief_descriptors`, `orb_features`, `hog_descriptor` |
| Matching | `template_match`, `feature_match` |
| Registration | `estimate_homography`, `localize_planar_object` |

세부 입력 계약과 주요 파라미터는
[`docs/image_processing_operations.md`](docs/image_processing_operations.md)를
참고하세요. 세 문서 기능의 프로젝트 배치는
[`docs/opencv_gui_feature_ml_extensions.md`](docs/opencv_gui_feature_ml_extensions.md)에
정리했습니다.
사진 편집, LUT, 합성, 비트 연산과 Photo 계열의 계약 및 예시는
[`docs/editing_filters_and_compositing.md`](docs/editing_filters_and_compositing.md)에
정리했습니다.

GUI 기능 중 파일/비디오 I/O는 `src/media_io`, 화면 표시·마우스·트랙바는
`src/ui`에 분리했습니다. HighGUI는 데스크톱 전용이며 headless 서버에서는 API
응답이나 Notebook 시각화를 사용합니다. kNN/SVM 학습과 모델 보관은
`src/machine_learning`에서 담당하고, 추론은 `model_predict` operation으로
Registry/Pipeline에 연결됩니다.

`SURF`와 `BRIEF`는 OpenCV contrib/nonfree 빌드 여부에 따라 사용할 수 있습니다.
기본 `opencv-python` 환경에서 지원되지 않으면 실행 결과에
`optional_dependency_unavailable` 오류가 명시적으로 반환됩니다.

기본 Pipeline Catalog에는 사진 편집, 문서·SEM 전처리, 검출·분할 및 합성용
20개 recipe가 등록됩니다.

| 구분 | 기본 Recipe |
|---|---|
| 사진 편집 | `natural_enhance`, `film_look`, `cinematic_3d_lut`, `vintage_1d_lut`, `clean_portrait`, `comic_style`, `pencil_sketch`, `dramatic_detail` |
| 분석·검사 | `edge_thumbnail`, `document_otsu`, `document_adaptive`, `binary_mask_cleanup`, `general_edge_detection`, `sem_profile_edges`, `reference_difference`, `line_detection`, `circle_detection`, `color_segmentation` |
| 합성 | `masked_local_enhancement`, `seamless_composite` |

각 recipe의 입력, 단계 및 출력은
[`docs/builtin_pipeline_recipes.md`](docs/builtin_pipeline_recipes.md)를 참고하세요.

### 5. Linear Pipeline Executor

- `PipelineSpec`과 순서가 보장된 `PipelineStepSpec`
- Pipeline 입력과 이전 step 출력의 명시적 binding
- 존재하지 않는 operation, 입력, 출력 및 호환되지 않는 kind 사전 검증
- 모든 step의 파라미터를 실행 전에 검증하여 부분 실행 방지
- 실패한 step에서 즉시 중단하고 원인 오류를 Pipeline 결과에 포함
- 최종 출력 미지정 시 마지막 step의 출력을 자동 사용
- 하나의 step 출력을 여러 후속 step에서 재사용 가능
- 참조 횟수를 기준으로 사용이 끝난 중간 결과를 즉시 해제
- `retain_intermediates=True`일 때만 디버깅용 중간 결과 보존
- 반복 실행용 `CompiledPipeline` 지원
- Registry가 변경되면 기존 compiled pipeline을 자동 재컴파일

### 6. FastAPI HTTP API

- Registry의 operation 목록·상세 조회 및 실행
- Model Registry의 모델 목록·상세 조회와 ID/version 입력 binding
- Pipeline Catalog의 pipeline 목록·상세 조회 및 실행
- 등록 전 PipelineSpec 사전 검증과 ad-hoc pipeline 실행
- 이미지 파일과 실행 명세를 함께 전달하는 `multipart/form-data` 입력
- PNG를 base64로 담은 JSON 또는 이미지와 manifest를 묶은 ZIP 출력
- 업로드 크기, 이미지 픽셀 수, 디코딩 메모리 및 응답 크기 제한
- 일관된 오류 응답과 OpenAPI 문서 제공
- built-in/user Recipe 조회·생성·복제·수정·삭제·실행 및 JSON 영속화
- 이미지별 Label 문서와 bbox/polygon/point/polyline annotation CRUD
- Recipe/Label revision 기반 충돌 감지(낙관적 잠금)

## 실행 흐름

```text
OperationRegistry.execute
    -> InputValidator
    -> ParameterValidator
    -> CrossParameterValidator
    -> OperationHandler
    -> OutputValidator
    -> ExecutionResult
```

## 기본 사용 예시

```python
import numpy as np

from src.registry import create_default_registry
from src.schemas import ColorSpace, ImageData


registry = create_default_registry()

image = ImageData(
    data=np.zeros((480, 640), dtype=np.uint8),
    color_space=ColorSpace.GRAY,
)

result = registry.execute(
    operation="gaussian_blur",
    inputs={"image": image},
    params={
        "kernel_size": 7,
        "sigma_x": 1.5,
    },
)

if result.success:
    output_image = result.output.images["image"]
else:
    print(result.error)
```

전체 실행 예시는 다음 명령으로 확인할 수 있습니다.

```bash
python -m examples.basic_registry_usage
python -m examples.opencv_extensions_usage
python -m examples.editing_filters_usage
```

## 사용자 정의 operation 등록

```python
registry.register(
    spec=MY_OPERATION_SPEC,
    handler=my_operation_handler,
)
```

또는 decorator를 사용할 수 있습니다.

```python
@registry.operation(MY_OPERATION_SPEC)
def my_operation_handler(*, inputs, params):
    return OperationOutput(...)
```

## Pipeline 사용 예시

```python
from src.pipeline import (
    PipelineExecutor,
    pipeline_input,
    step_output,
)
from src.registry import create_default_registry
from src.schemas import (
    InputKind,
    InputSlotSpec,
    PipelineSpec,
    PipelineStepSpec,
)


pipeline = PipelineSpec(
    name="edge_thumbnail",
    display_name="Edge Thumbnail",
    inputs=[
        InputSlotSpec(name="image", kind=InputKind.IMAGE)
    ],
    steps=[
        PipelineStepSpec(
            id="gray",
            operation="convert_color",
            inputs={"image": pipeline_input("image")},
            params={"target_color_space": "gray"},
        ),
        PipelineStepSpec(
            id="blur",
            operation="gaussian_blur",
            inputs={"image": step_output("gray")},
            params={"kernel_size": 5},
        ),
        PipelineStepSpec(
            id="resize",
            operation="resize",
            inputs={"image": step_output("blur")},
            params={"width": 320, "height": 240},
        ),
        PipelineStepSpec(
            id="edges",
            operation="canny",
            inputs={"image": step_output("resize")},
        ),
    ],
    outputs={"edges": step_output("edges")},
)

executor = PipelineExecutor(create_default_registry())
compiled = executor.compile(pipeline)

result = executor.execute(
    pipeline=compiled,
    inputs={"image": image},
)
```

전체 Pipeline 예시는 다음 명령으로 실행합니다.

```bash
python -m examples.pipeline_usage
```

## FastAPI 실행

의존성을 설치하고 프로젝트 루트에서 서버를 시작합니다.

```bash
python -m pip install -r requirements.txt
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

서버가 실행되면 Swagger UI는 `http://localhost:8000/docs`, OpenAPI JSON은
`http://localhost:8000/openapi.json`에서 확인할 수 있습니다.

### Jupyter Notebook으로 전처리 결과 확인

[`notebooks/api_preprocessing_demo.ipynb`](notebooks/api_preprocessing_demo.ipynb)는
이미지를 로드해 개별 operation과 기본 Pipeline을 API로 실행하고 원본·결과·중간
단계를 Matplotlib으로 비교합니다.

API 서버를 실행한 상태에서 다른 터미널을 열어 다음 명령을 실행합니다.

```bash
python -m jupyter lab
```

Notebook 상단의 `IMAGE_PATH`를 자신의 PNG/JPEG/TIFF 등의 이미지 경로로
변경하면 됩니다. 값을 `None`으로 두면 내장 데모 이미지를 사용합니다.

### Endpoint

| Method | Path | 기능 |
|---|---|---|
| `GET` | `/api/v1/health` | 상태 확인 |
| `GET` | `/api/v1/operations` | operation 목록 조회 |
| `GET` | `/api/v1/operations/{name}` | operation 상세 조회 |
| `POST` | `/api/v1/operations/{name}/execute` | operation 실행 |
| `GET` | `/api/v1/models` | 등록 모델 목록 조회 |
| `GET` | `/api/v1/models/{model_id}/{version}` | 등록 모델 상세 조회 |
| `GET` | `/api/v1/pipelines` | 등록된 pipeline 목록 조회 |
| `GET` | `/api/v1/pipelines/{name}` | pipeline 상세 조회 |
| `POST` | `/api/v1/pipelines/validate` | PipelineSpec 사전 검증 |
| `POST` | `/api/v1/pipelines/execute` | ad-hoc pipeline 실행 |
| `POST` | `/api/v1/pipelines/{name}/execute` | 등록된 pipeline 실행 |
| `GET` | `/api/v1/recipes` | Recipe 목록/검색 (`builtin`, `user`) |
| `POST` | `/api/v1/recipes` | 사용자 Recipe 생성 |
| `GET` | `/api/v1/recipes/{name}` | Recipe 상세 조회 |
| `POST` | `/api/v1/recipes/{name}/clone` | built-in/user Recipe를 사용자 Recipe로 복제 |
| `PUT` | `/api/v1/recipes/{name}` | 사용자 Recipe 수정 |
| `DELETE` | `/api/v1/recipes/{name}` | 사용자 Recipe 삭제 |
| `POST` | `/api/v1/recipes/{name}/execute` | Recipe 실행 |
| `GET` | `/api/v1/labels` | Label 문서 목록/검색/페이징 |
| `POST` | `/api/v1/labels` | 이미지 Label 문서 생성 |
| `GET` | `/api/v1/labels/classes` | 현재 annotation class 통계 |
| `GET` | `/api/v1/labels/{image_id}` | 이미지 Label 문서 조회 |
| `PUT` | `/api/v1/labels/{image_id}` | 이미지 Label 문서 전체 수정 |
| `DELETE` | `/api/v1/labels/{image_id}` | 이미지 Label 문서 삭제 |
| `POST` | `/api/v1/labels/{image_id}/annotations` | annotation 추가 |
| `PUT` | `/api/v1/labels/{image_id}/annotations/{annotation_id}` | annotation 수정 |
| `DELETE` | `/api/v1/labels/{image_id}/annotations/{annotation_id}` | annotation 삭제 |

실행 endpoint는 `payload`라는 JSON 문자열 form field와 0개 이상의 `files`
field를 받습니다. `image_inputs[].file_index`는 `files`의 순서를 가리킵니다.
서버 시작 시 `create_app(models=[...])`로 등록한 모델은 `model_inputs`의
`model_id`와 `version`으로 실행 입력에 연결합니다.

예를 들어 Gaussian Blur를 실행하려면 다음과 같이 요청합니다.

```bash
curl -X POST \
  'http://localhost:8000/api/v1/operations/gaussian_blur/execute' \
  -F 'payload={"params":{"kernel_size":5},"image_inputs":[{"input_name":"image","file_index":0}]}' \
  -F 'files=@input.png;type=image/png'
```

기본 응답은 출력 PNG가 base64로 포함된 JSON입니다. 큰 이미지나 여러 중간
결과를 받을 때는 ZIP 응답을 권장합니다.

```bash
curl -X POST \
  'http://localhost:8000/api/v1/pipelines/edge_thumbnail/execute?response_format=zip' \
  -F 'payload={"image_inputs":[{"input_name":"image","file_index":0}],"retain_intermediates":true}' \
  -F 'files=@input.png;type=image/png' \
  --output result.zip
```

기본 `src.main:app`에는 20개 built-in recipe가 등록됩니다. 애플리케이션 생성 시
목록을 전달하면 기본값 대신 원하는 pipeline만 등록할 수 있습니다.

```python
from src.api import create_app

app = create_app(pipelines=[EDGE_THUMBNAIL_PIPELINE])
```

등록하지 않은 PipelineSpec은 `/api/v1/pipelines/validate`로 먼저 검사하고
`/api/v1/pipelines/execute`에서 바로 실행할 수도 있습니다.

### Recipe / Label 저장 위치

사용자 Recipe와 Label 데이터는 기본적으로 프로젝트 실행 경로의
`.image_processing_data/` 아래에 JSON으로 저장됩니다. built-in 20개 Recipe는
소스 코드에서 생성되며 읽기 전용이고, `/recipes/{name}/clone`으로 사용자 Recipe를
만든 뒤 수정할 수 있습니다. 저장 경로는 `ApiSettings`에서 변경할 수 있습니다.

```python
from pathlib import Path

from src.api import ApiSettings, create_app

settings = ApiSettings(
    recipe_store_dir=Path(r"D:/ImageStudioData/recipes"),
    label_store_dir=Path(r"D:/ImageStudioData/labels"),
)
app = create_app(settings=settings)
```

Recipe와 Label 모두 `revision`을 사용합니다. 수정/삭제 시 `expected_revision`을
전달하면 다른 화면이나 세션에서 먼저 저장한 변경사항을 덮어쓰는 것을 방지할 수
있습니다. Label 좌표는 pixel 좌표이며 이미지 `width`/`height` 범위를 벗어나는
bbox, polygon, point, polyline은 저장되지 않습니다. 자세한 요청/응답 예시는
[`docs/recipe_and_label_api.md`](docs/recipe_and_label_api.md)를 참고하세요.

## 테스트 실행

프로젝트 루트에서 다음을 실행합니다.

```bash
python -m pytest -q
```

현재 테스트는 스키마, 개별/교차 파라미터, 입력/출력 계약, Registry,
Pipeline 사전 검증, 순차·분기형 참조, 실패 중단, 중간 결과 관리, 실제
OpenCV 통합 실행, HTTP 조회·실행, multipart 이미지 업로드, JSON/ZIP 출력, Recipe 영속화/복제/
revision 충돌, Label/annotation CRUD·좌표 검증·영속화와 오류 상태 코드뿐 아니라
Feature2D, homography, K-Means, kNN/SVM 및 Unicode 이미지 I/O도 확인합니다.

## 다음 단계

작업 상태 저장, 비동기 실행과 결과 조회가 필요한 경우 job queue 계층을
추가할 수 있습니다.
