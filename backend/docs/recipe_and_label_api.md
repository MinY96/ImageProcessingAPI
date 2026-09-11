# Recipe / Label API

프론트엔드의 Recipe Editor와 Image Labeling 화면에서 직접 사용하기 위한 API입니다.

## 1. Recipe 모델

Recipe API는 이제 두 실행 정의를 하나의 모델로 관리합니다.

- `kind=linear`: 기존 `PipelineSpec`
- `kind=graph`: DAG 기반 `GraphRecipeSpec`

기존 클라이언트가 `pipeline`만 전송하면 `kind=linear`로 자동 추론하므로 이전 API와
호환됩니다. Graph Recipe는 `graph` 필드를 사용합니다.

Linear Recipe 예:

```json
{
  "name": "sem_edge_custom",
  "kind": "linear",
  "pipeline": {
    "name": "sem_edge_custom",
    "display_name": "SEM Edge Custom",
    "version": "1.0.0",
    "inputs": [],
    "steps": [],
    "outputs": {}
  },
  "graph": null,
  "source": "user",
  "readonly": false,
  "tags": ["sem"],
  "revision": 1
}
```

Graph Recipe 예:

```json
{
  "name": "sem_rule_custom",
  "kind": "graph",
  "pipeline": null,
  "graph": {
    "name": "sem_rule_custom",
    "display_name": "SEM Rule Custom",
    "version": "1.0.0",
    "inputs": [{"name": "image", "kind": "image"}],
    "nodes": [],
    "outputs": {}
  },
  "source": "user",
  "readonly": false,
  "revision": 1
}
```

기본 Recipe는 **20개 Linear + 5개 Graph**이며 모두 `source=builtin`,
`readonly=true`입니다. Graph 구조/Feature/ROI/SubRecipe에 대한 상세 설명은
[`graph_workflow_api.md`](graph_workflow_api.md)를 참고하세요.

### 기본 Recipe 복제


```http
POST /api/v1/recipes/sem_profile_edges/clone
Content-Type: application/json
```

```json
{
  "name": "sem_profile_edges_v2",
  "display_name": "SEM Profile Edges V2",
  "tags": ["sem", "inspection"]
}
```

### 사용자 Recipe 생성

```http
POST /api/v1/recipes
```

```json
{
  "pipeline": {
    "name": "my_recipe",
    "display_name": "My Recipe",
    "version": "1.0.0",
    "inputs": [],
    "steps": [
      {
        "id": "step1",
        "operation": "invert",
        "inputs": {},
        "params": {}
      }
    ],
    "outputs": {}
  },
  "tags": ["custom"]
}
```

Linear Recipe는 저장 전에 `PipelineExecutor.compile()`, Graph Recipe는
`WorkflowExecutor.compile()` 검증을 통과해야 합니다. Linear는 Pipeline Catalog, Graph는
Workflow Catalog에 등록되어 반복 실행 시 compiled 정의를 재사용합니다.

### Recipe 수정 충돌 방지

```http
PUT /api/v1/recipes/my_recipe
```

```json
{
  "kind": "linear",
  "pipeline": { "...": "전체 PipelineSpec" },
  "tags": ["custom", "edited"],
  "expected_revision": 3
}
```

서버 revision이 이미 4라면 `409 recipe_revision_conflict`를 반환합니다.

### Recipe 실행

Linear/Graph 모두 기존 Pipeline 실행 API와 같은 multipart 계약을 사용합니다. 서버는
Recipe의 `kind`를 보고 적절한 Executor를 자동 선택합니다.

```http
POST /api/v1/recipes/my_recipe/execute
```

`payload`에는 `PipelineRunPayload` JSON 문자열을 넣고 이미지는 `files`로
전송합니다. `retain_intermediates=true`도 그대로 사용할 수 있습니다.

---

## 2. Label 모델

이미지 원본 자체를 Label API가 복제 저장하지는 않습니다. Label API는 이미지
식별정보와 annotation을 저장합니다. `source_uri`에는 로컬 파일의 상대경로,
Dataset 내 논리 경로 등을 기록할 수 있습니다.

지원 annotation:

- `bbox`: 사각형
- `polygon`: 3점 이상의 다각형
- `point`: 단일 점
- `polyline`: 2점 이상의 선

좌표는 pixel 좌표입니다.

### Label 문서 생성

```http
POST /api/v1/labels
```

```json
{
  "image_id": "sem_000001",
  "image_name": "SEM_000001.png",
  "source_uri": "dataset/SEM_000001.png",
  "width": 1280,
  "height": 960,
  "tags": ["training"],
  "metadata": {
    "equipment": "SEM01"
  },
  "annotations": [
    {
      "type": "bbox",
      "label": "bridge",
      "x": 120,
      "y": 80,
      "width": 240,
      "height": 160
    },
    {
      "type": "polygon",
      "label": "residue",
      "points": [
        {"x": 400, "y": 300},
        {"x": 470, "y": 310},
        {"x": 450, "y": 390}
      ]
    }
  ]
}
```

`image_id`를 생략하면 서버가 UUID 기반 ID를 생성합니다. `annotation_id`도
생략하면 서버가 자동 생성합니다.

### Annotation 추가

```http
POST /api/v1/labels/sem_000001/annotations
```

```json
{
  "expected_revision": 1,
  "annotation": {
    "type": "point",
    "label": "measurement_point",
    "point": {"x": 640, "y": 480}
  }
}
```

추가/수정/삭제 성공 시 최신 전체 `LabelDocument`를 반환하므로 프론트엔드는
응답의 `annotations`와 `revision`을 그대로 상태에 반영하면 됩니다.

### Label 목록

```http
GET /api/v1/labels?offset=0&limit=100&label=bridge&tag=training&search=SEM01
```

목록 응답에는 전체 annotation 대신 `annotation_count`, 사용 label 목록,
최종 수정 시각만 포함한 summary를 반환합니다.

### Label class 통계

```http
GET /api/v1/labels/classes
```

현재 저장된 annotation을 기준으로 label별 annotation 수와 이미지 수를 반환합니다.
프론트엔드의 class dropdown이나 dataset summary에 사용할 수 있습니다.

---

## 3. 저장 방식

기본 경로:

```text
.image_processing_data/
├─ recipes/
│  └─ <recipe_name>.json
└─ labels/
   └─ <sha256(image_id)>.json
```

쓰기 작업은 임시 파일 작성 후 `os.replace()`로 교체하여 중간에 파일이 반쪽만
저장되는 가능성을 줄입니다. Label 파일명에는 `image_id` 원문을 사용하지 않고
SHA-256을 사용하여 경로 조작 문제를 막습니다.

JSON-per-image 방식은 로컬 프로그램에서 Dataset 파일과 함께 백업/이동하기 쉽다는
장점이 있습니다. 수십만~수백만 이미지의 중앙 다중 사용자 Dataset으로 확장할 때는
동일한 Service API를 유지하면서 Store만 SQLite/PostgreSQL/Object Storage 기반으로
교체하는 것이 권장됩니다.
