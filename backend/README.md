# Image Processing API Project

OpenCV 기반 이미지 처리 기능을 공통 스키마, 검증기, Registry 및 API로
확장하고, 전처리 → ROI/분기 → Feature 추출 → Scalar 연산 → Rule 판정까지
구성할 수 있는 Rule-based Vision Workflow 프로젝트입니다.

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

OpenCV 4.14 계열의 Image Processing, GUI, Feature2D, Machine Learning 기능을
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

### 6. Graph Workflow / Rule Engine

기존 선형 Pipeline 위에 DAG 기반 `GraphRecipeSpec` 실행 계층을 추가했습니다. 하나의
output을 여러 branch가 공유할 수 있고, ROI별 서로 다른 처리, feature 추출/연산,
최종 threshold 판정, linear/graph SubRecipe 재사용을 지원합니다.

- Typed Port: `image`, `mask`, `profile`, `scalar`, `roi`, `boolean`, `decision` 등
- Node: Operation, Feature, Scalar Operator, ROI Crop/Compose, Decision, SubRecipe
- Graph cycle 및 잘못된 port 연결을 실행 전에 검증
- Feature Registry: pixel/profile/contour/image similarity/mask similarity
- Scalar Operator Registry: 산술, ratio, abs diff, sum/mean/min/max, weighted sum/mean, normalize
- 참조 횟수 기반 중간 결과 해제로 branch 수 증가 시 불필요한 이미지 복사/보존 최소화
- Recipe API에서 `kind=linear|graph`를 동일하게 조회·저장·복제·수정·실행

기본 Graph Recipe 5개를 함께 제공합니다.

| Recipe | 구조 |
|---|---|
| `rule_branch_binary_score` | Binary 이후 3-way branch → 3 feature → weighted score → 판정 |
| `rule_multi_roi_fusion` | 좌/중/우 ROI → 각기 다른 pipeline → feature fusion → 판정 |
| `rule_multi_roi_recompose` | ROI별 서로 다른 전처리 → 원 좌표에 image recompose |
| `rule_nested_sem_profile` | 기존 linear `sem_profile_edges`를 SubRecipe로 사용 |
| `rule_nested_graph_score` | Graph Recipe 안에 다른 Graph Recipe를 SubRecipe로 사용 |

상세 구조와 JSON/API 사용법은
[`docs/graph_workflow_api.md`](docs/graph_workflow_api.md)를 참고하세요.

전체 Python 실행 예시는 다음 명령으로 확인할 수 있습니다.

```bash
python -m examples.graph_workflow_usage
```

### 7. TestDataset / Evaluation Job Engine

Decision까지 포함된 Recipe를 실제 OK/NG 이미지 폴더에 일괄 적용해 성능을 검증합니다.
Evaluation은 v0.6.0부터 **로컬 Job Queue + 전용 Worker** 구조로 실행됩니다.

- 이미지 폴더 기반 TestDataset 생성 및 JSON 영속화
- `OK/`, `NG/` 하위 폴더 Ground Truth 자동 인식
- 개별/다중 Ground Truth 수정 및 revision 충돌 감지
- 큰 Dataset용 이미지 목록 pagination/filter
- `POST /evaluations` 즉시 `202 Accepted` + `evaluation_id` 반환
- `queued / running / completed / failed / cancel_requested / cancelled` 상태 관리
- live progress(`processed / total / percent`) 조회
- 기본 Worker 1개로 무거운 Evaluation과 Interactive API 실행 분리
- 기본 50장 단위 결과 checkpoint 저장
- queued Job 재시작 복구, 중단된 running Job 자동 failed 정리
- 실행 직전 Dataset/Recipe revision 재검증으로 Queue 대기 중 변경 보호
- 실행 중 안전한 cancel 요청 지원
- Graph/Linear Recipe batch 실행
- Decision output + Score output 추출
- Graph/Pipeline intermediate의 scalar 값만 오판 분석용으로 저장
- TP/TN/FP/FN, Accuracy, Precision, Recall, Specificity, F1
- 평균/중앙값/P95/최대 처리시간과 OK/NG score 분포 통계
- 손상 이미지/실행 실패를 `ERROR`로 분리하여 metric 왜곡 방지
- Dataset revision + Recipe kind/version/revision snapshot 저장
- False NG / Missed NG / ERROR 결과 filtering 및 pagination

상세 API와 프론트엔드 연계 방식은
[`docs/evaluation_api.md`](docs/evaluation_api.md)를 참고하세요.

### 8. FastAPI HTTP API

- Registry의 operation 목록·상세 조회 및 실행
- Model Registry의 모델 목록·상세 조회와 ID/version 입력 binding
- Pipeline Catalog의 pipeline 목록·상세 조회 및 실행
- 등록 전 PipelineSpec 사전 검증과 ad-hoc pipeline 실행
- 이미지 파일과 실행 명세를 함께 전달하는 `multipart/form-data` 입력
- PNG를 base64로 담은 JSON 또는 이미지와 manifest를 묶은 ZIP 출력
- 업로드 크기, 이미지 픽셀 수, 디코딩 메모리 및 응답 크기 제한
- 일관된 오류 응답과 OpenAPI 문서 제공
- built-in/user Recipe 조회·생성·복제·수정·삭제·실행 및 JSON 영속화
- Recipe를 `kind=linear|graph`로 통합하고 동일 `/recipes/{name}/execute`에서 자동 실행
- Graph Feature/Scalar Operator metadata 조회, Graph compile 검증 및 ad-hoc 실행 API
- 이미지별 Label 문서와 bbox/polygon/point/polyline annotation CRUD
- Recipe/Label revision 기반 충돌 감지(낙관적 잠금)
- 원본/전처리 결과 공통 Image Analysis API: 기본 메타데이터, Gray/RGB/HSV histogram, 통계 특징, X/Y projection 및 미분 profile
- Operation/Pipeline/Recipe 실행 결과에 선택적으로 분석정보를 함께 반환
- TestDataset 폴더 import/OK·NG Ground Truth 관리 및 비동기 Evaluation Job Queue API

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

현재 FastAPI application version은 `0.6.0`이며 HTTP endpoint는 총 49개입니다.

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
| `POST` | `/api/v1/analysis/image` | 업로드 이미지 기본/통계/히스토그램/프로파일 분석 |
| `GET` | `/api/v1/pipelines` | 등록된 pipeline 목록 조회 |
| `GET` | `/api/v1/pipelines/{name}` | pipeline 상세 조회 |
| `POST` | `/api/v1/pipelines/validate` | PipelineSpec 사전 검증 |
| `POST` | `/api/v1/pipelines/execute` | ad-hoc pipeline 실행 |
| `POST` | `/api/v1/pipelines/{name}/execute` | 등록된 pipeline 실행 |
| `GET` | `/api/v1/workflow/features` | Feature Extractor 목록/스키마 조회 |
| `GET` | `/api/v1/workflow/operators` | Scalar Operator 목록/스키마 조회 |
| `POST` | `/api/v1/workflow/validate` | GraphRecipeSpec DAG 사전 검증 |
| `POST` | `/api/v1/workflow/execute` | ad-hoc Graph Recipe 실행 |
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
| `GET` | `/api/v1/test-datasets` | TestDataset 요약 목록 |
| `POST` | `/api/v1/test-datasets` | TestDataset 생성 |
| `GET` | `/api/v1/test-datasets/{id}` | TestDataset 요약 조회 |
| `PUT` | `/api/v1/test-datasets/{id}` | TestDataset 정보 수정 |
| `DELETE` | `/api/v1/test-datasets/{id}` | TestDataset 삭제 |
| `POST` | `/api/v1/test-datasets/{id}/import-folder` | 폴더 이미지 가져오기 및 OK/NG 자동 라벨 |
| `GET` | `/api/v1/test-datasets/{id}/images` | Dataset 이미지 목록/필터/pagination |
| `POST` | `/api/v1/test-datasets/{id}/images` | Dataset에 이미지 경로 추가 |
| `PUT` | `/api/v1/test-datasets/{id}/images/{image_id}` | 이미지 Ground Truth/metadata 수정 |
| `DELETE` | `/api/v1/test-datasets/{id}/images/{image_id}` | Dataset 이미지 제거 |
| `PUT` | `/api/v1/test-datasets/{id}/ground-truth` | 다중 Ground Truth 변경 |
| `GET` | `/api/v1/evaluations` | Evaluation Job/이력 조회 및 상태 필터 |
| `POST` | `/api/v1/evaluations` | Evaluation Job 등록 (`202 Accepted`) |
| `POST` | `/api/v1/evaluations/{id}/cancel` | queued/running 평가 취소 요청 |
| `GET` | `/api/v1/evaluations/{id}` | 평가 상태/진행률/결과 조회 |
| `DELETE` | `/api/v1/evaluations/{id}` | terminal 평가 이력 삭제 |
| `GET` | `/api/v1/evaluations/{id}/results` | FP/FN/ERROR 등 이미지별 결과 필터 |

실행 endpoint는 `payload`라는 JSON 문자열 form field와 0개 이상의 `files`
field를 받습니다. `image_inputs[].file_index`는 `files`의 순서를 가리킵니다.
서버 시작 시 `create_app(models=[...])`로 등록한 모델은 `model_inputs`의
`model_id`와 `version`으로 실행 입력에 연결합니다.

이미지 자체의 분석만 필요하면 `/api/v1/analysis/image`를 사용합니다. 실행 결과까지
분석하려면 Operation/Pipeline/Recipe payload에 `analysis` 옵션을 포함합니다. Pipeline의
중간 결과는 `analyze_intermediates=true`일 때만 분석하여 불필요한 CPU/메모리 사용을
줄입니다. 자세한 필드와 프론트엔드 권장 표시 방법은
[`docs/image_analysis_api.md`](docs/image_analysis_api.md)를 참고하세요.

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

기본 `src.main:app`에는 20개 linear built-in recipe와 5개 graph built-in recipe가 등록됩니다. 애플리케이션 생성 시
목록을 전달하면 기본값 대신 원하는 pipeline만 등록할 수 있습니다.

```python
from src.api import create_app

app = create_app(pipelines=[EDGE_THUMBNAIL_PIPELINE])
```

등록하지 않은 PipelineSpec은 `/api/v1/pipelines/validate`로 먼저 검사하고
`/api/v1/pipelines/execute`에서 바로 실행할 수도 있습니다.

### Recipe / Label 저장 위치

사용자 Recipe와 Label 데이터는 기본적으로 프로젝트 실행 경로의
`.image_processing_data/` 아래에 JSON으로 저장됩니다. built-in 20개 Linear Recipe와
5개 Graph Recipe는 소스 코드에서 생성되며 읽기 전용이고, `/recipes/{name}/clone`으로
`linear`/`graph` 종류를 유지한 사용자 Recipe를 만든 뒤 수정할 수 있습니다.
저장 경로는 `ApiSettings`에서 변경할 수 있습니다.

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

현재 168개 테스트는 스키마, 개별/교차 파라미터, 입력/출력 계약, Registry,
Pipeline 사전 검증, 순차·분기형 참조, 실패 중단, 중간 결과 관리, Graph DAG cycle/typed-port 검증,
Binary 다중 분기/ROI fusion/ROI recompose/SubRecipe 실행, 실제 OpenCV 통합 실행, HTTP 조회·실행,
multipart 이미지 업로드, JSON/ZIP 출력, Recipe 영속화/복제/
revision 충돌, Label/annotation CRUD·좌표 검증·영속화와 오류 상태 코드뿐 아니라
Feature2D, homography, K-Means, kNN/SVM 및 Unicode 이미지 I/O도 확인합니다.

## 다음 단계

작업 상태 저장, 비동기 실행과 결과 조회가 필요한 경우 job queue 계층을
추가할 수 있습니다.
