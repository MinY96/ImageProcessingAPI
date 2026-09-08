# Graph Workflow / Rule Recipe API

## 1. 목적

기존 `PipelineSpec`은 순차적인 이미지 처리에 적합하지만, 실제 rule-based vision 검사에서는 다음 구조가 필요합니다.

- 하나의 이미지/마스크를 여러 branch가 공유
- 여러 ROI를 서로 다른 pipeline으로 처리
- 각 branch에서 scalar feature를 추출하고 다시 연산
- 최종 scalar를 threshold/range로 판정
- 기존 linear recipe 또는 graph recipe를 다른 recipe 안에서 재사용

이 프로젝트에서는 이를 `GraphRecipeSpec` 기반 DAG(Directed Acyclic Graph)로 표현합니다.
기존 20개 `PipelineSpec` recipe는 그대로 유지하며, Recipe API에서는 `kind=linear|graph`로 통합 조회/실행합니다.

## 2. 실행 모델

```text
Graph Inputs
    ↓
Typed Nodes + Typed Ports
    ↓
Topological validation / compile
    ↓
WorkflowExecutor
    ↓
Image outputs + scalar/data outputs
```

Graph의 한 output port는 여러 node input으로 연결할 수 있으므로 별도 Branch node는 필요하지 않습니다.

```text
                    ┌─> branch A ─> feature A ─┐
image -> binary ----┼─> branch B ─> feature B ─┼─> scalar operator -> decision
                    └─> branch C ─> feature C ─┘
```

실행 순서는 topological sort로 결정되며 cycle은 저장/실행 전에 거부됩니다.

## 3. 데이터 종류(Port Kind)

`WorkflowDataKind`는 node 간 잘못된 연결을 compile 단계에서 막기 위한 타입입니다.

- `image`, `mask`, `template`
- `array`, `profile`
- `contours`, `metrics`
- `scalar`, `boolean`, `decision`
- `roi`, `roi_set`

예를 들어 `pixel_statistic.value`는 `scalar`이므로 `gaussian_blur.image`에 연결할 수 없습니다.

## 4. Node 종류

### Operation

기존 `OperationRegistry`의 64개 OpenCV operation을 그대로 사용합니다.

```json
{
  "id": "blur",
  "node_type": "operation",
  "operation": "gaussian_blur",
  "inputs": {
    "image": {"type": "node_output", "node_id": "gray", "output_name": "image"}
  },
  "params": {"kernel_size": 5}
}
```

### Feature

이미지/마스크에서 최종 rule에 사용할 feature를 추출합니다.

현재 기본 Feature Registry:

| Feature | 대표 기능 |
|---|---|
| `pixel_statistic` | sum/mean/min/max/median/std/variance/percentile/nonzero count/ratio |
| `profile_feature` | X/Y projection, derivative, peak count/height/prominence |
| `contour_feature` | contour count, largest/total area, area ratio, perimeter, circularity, solidity |
| `image_similarity` | MAE/MSE/RMSE/NCC/global SSIM |
| `mask_similarity` | IoU/Dice/mismatch ratio |

모든 Feature node는 최소 하나 이상의 typed output을 반환하며, 판정용 feature는 일반적으로 `value: scalar`입니다.

### Scalar Operator

여러 feature 값을 최종 score로 합칩니다.

- `add`, `subtract`, `multiply`, `divide`, `ratio`, `abs_diff`
- `sum`, `mean`, `min`, `max`
- `weighted_sum`, `weighted_mean`
- `normalize_range`

예:

```text
score = 0.45 * foreground_ratio
      + 0.25 * boundary_ratio
      + 0.30 * largest_area_ratio
```

### ROI Crop / Compose

`roi_crop`은 pixel 또는 relative 좌표로 영역을 자르고 `image`와 `region` metadata를 반환합니다.
`region`에는 원본 좌표계의 `x/y/width/height/source_width/source_height`가 유지됩니다.

`roi_compose`는 처리된 patch를 해당 ROI 위치에 다시 합성합니다.

### Decision

현재 scalar 비교를 지원합니다.

- `gt`, `gte`, `lt`, `lte`
- `inside_range`, `outside_range`

출력:

- `value: scalar`
- `passed: boolean`
- `label: decision` (`OK`/`NG` 기본)

### SubRecipe

기존 linear `PipelineSpec`과 graph `GraphRecipeSpec`을 하나의 node처럼 호출합니다.

```json
{
  "id": "profile",
  "node_type": "subrecipe",
  "recipe": "sem_profile_edges",
  "recipe_kind": "linear",
  "recipe_version": "1.0.0",
  "inputs": {
    "image": {"type": "graph_input", "input_name": "image"}
  }
}
```

`recipe_version`을 지정하면 현재 등록된 recipe version과 다를 때 validation에 실패합니다.
SubRecipe dependency에서도 cycle을 검사하여 `A -> B -> A` 형태를 차단합니다.

## 5. Built-in Graph Recipe 예시

### `rule_branch_binary_score`

사용자가 요청한 **Binary 이후 동일 이미지를 N개 branch로 분기하여 서로 다른 feature를 추출한 뒤 합치는 예시**입니다.

```text
Image -> Gray -> Otsu Binary
                   ├─> Morph Open     -> Foreground Ratio ─┐
                   ├─> Morph Gradient -> Boundary Ratio ───┼─> Weighted Sum -> Decision
                   └─> Morph Close    -> Largest Area Ratio┘
```

Graph output은 `binary`, 세 feature, `score`, `passed`, `result`입니다.

### `rule_multi_roi_fusion`

사용자가 요청한 **N개 ROI가 각각 다른 pipeline을 거친 뒤 feature 수준에서 다시 합류하는 예시**입니다.

```text
                  ┌─ Left ROI   -> Gray -> Gaussian -> Mean -> Normalize ─┐
Image ------------├─ Center ROI -> Gray -> CLAHE    -> Mean -> Normalize ─┼─> Weighted Mean -> Decision
                  └─ Right ROI  -> Gray -> Canny    -> Edge Ratio ────────┘
```

### `rule_multi_roi_recompose`

ROI별 처리 결과를 원래 이미지 좌표에 다시 합치는 image-level merge 예시입니다.

```text
Image -> Gray
          ├─ Left ROI   -> Gaussian ─┐
          ├─ Center ROI -> CLAHE ────┼─> ROI Compose -> Full Image
          └─ Right ROI  -> Median ───┘
```

### `rule_nested_sem_profile`

기존 linear recipe인 `sem_profile_edges`를 Graph 내부에서 SubRecipe로 호출합니다.

```text
Image -> [SubRecipe: sem_profile_edges] -> profile_mask -> pixel ratio -> Decision
```

### `rule_nested_graph_score`

Graph Recipe 안에 다른 Graph Recipe 전체를 넣는 예시입니다.

```text
Image -> [SubRecipe: rule_branch_binary_score] -> score -> stricter Decision
```

## 6. API

### Metadata

- `GET /api/v1/workflow/features`
- `GET /api/v1/workflow/operators`

React Flow의 Feature/Operator node library와 parameter UI 구성에 사용할 수 있습니다.

### Graph 사전 검증

- `POST /api/v1/workflow/validate`

검증 항목:

- graph cycle
- 존재하지 않는 graph input/node/output
- port kind 호환성
- operation/feature/operator 존재 여부
- node parameter 유효성
- ROI parameter
- decision parameter
- SubRecipe 존재 여부 / version / recursive dependency

### Ad-hoc Graph 실행

- `POST /api/v1/workflow/execute`

`payload` form field에 `AdHocWorkflowRunPayload` JSON을 넣고 이미지는 기존 Pipeline API와 동일하게 `files`로 전달합니다.

### Recipe API 통합

Graph Recipe도 기존 Recipe endpoint를 그대로 사용합니다.

- `GET /api/v1/recipes?kind=graph`
- `POST /api/v1/recipes`
- `GET /api/v1/recipes/{name}`
- `POST /api/v1/recipes/{name}/clone`
- `PUT /api/v1/recipes/{name}`
- `DELETE /api/v1/recipes/{name}`
- `POST /api/v1/recipes/{name}/execute`

사용자 저장 JSON에서는 `kind: "graph"`와 `graph: {...}`를 사용합니다.

## 7. 성능/메모리 정책

Graph 실행기는 모든 node output을 끝까지 보존하지 않습니다.
각 output reference가 앞으로 몇 번 더 사용되는지 계산하고, 마지막 consumer가 사용한 뒤 `retain_intermediates=false`이면 즉시 해제합니다.

따라서 Binary output 하나가 3개 branch에서 공유될 때 input image를 branch 수만큼 복사하지 않고 같은 `ImageData`를 읽기 전용으로 전달합니다.
ROI crop은 원본의 대형 배열을 장기간 붙잡는 NumPy view 문제를 피하기 위해 crop 결과만 복사합니다.

`retain_intermediates=true`는 디버깅/GUI preview 목적일 때만 사용하십시오.

## 8. 향후 확장 포인트

현재 schema에는 `roi_set`, `contours`, `profile` 등의 종류가 미리 정의되어 있습니다.
다음 확장에서는 다음 node를 추가할 수 있습니다.

- Dynamic ROI / ROI_SET 생성
- ROI_SET에 동일 SubRecipe를 map하는 반복 node
- contour distance / Hausdorff / fitting / GLCM / FFT feature
- conditional/select node
- 독립 branch 병렬 실행

이 확장들도 GraphRecipeSpec 형식은 유지한 채 Registry/Executor node handler만 추가하는 방향으로 구현할 수 있습니다.
