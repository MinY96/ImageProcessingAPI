# TestDataset / Evaluation API

`TestDataset`과 `EvaluationRun`은 Decision까지 포함된 Rule Recipe를 실제 OK/NG 이미지 집합에 일괄 적용해 성능을 검증하기 위한 계층입니다.

```text
Image Folder
   ↓
TestDataset (Ground Truth: OK / NG)
   ↓
Recipe (Decision output 포함)
   ↓
EvaluationEngine
   ↓
Prediction + Score + Node scalar values + latency
   ↓
Confusion Matrix / Accuracy / Precision / Recall / Specificity / F1
```

## 저장 위치

기본 로컬 저장 위치는 다음과 같습니다.

```text
.image_processing_data/
├─ test_datasets/
└─ evaluations/
```

두 저장소 모두 JSON + 임시파일 + `os.replace()` 방식의 원자적 저장을 사용합니다.

## 1. TestDataset

### Dataset 생성

```http
POST /api/v1/test-datasets
Content-Type: application/json
```

```json
{
  "dataset_id": "sem_bridge_validation_01",
  "name": "SEM Bridge Validation 01",
  "description": "Recipe 검증용 OK/NG 데이터"
}
```

### 폴더 가져오기

```http
POST /api/v1/test-datasets/sem_bridge_validation_01/import-folder
```

```json
{
  "folder_path": "C:/SEM/TestSet_01",
  "recursive": true,
  "auto_label_from_parent": true
}
```

기본적으로 다음 구조를 자동 인식합니다.

```text
C:/SEM/TestSet_01/
├─ OK/
│  ├─ 001.png
│  └─ 002.png
└─ NG/
   ├─ 101.png
   └─ 102.png
```

`OK` 폴더 이미지는 `GroundTruth=OK`, `NG` 폴더 이미지는 `GroundTruth=NG`가 됩니다. 다른 폴더의 이미지는 `null(Unlabeled)`로 등록됩니다.

폴더명이 다른 경우 `label_mapping`을 지정할 수 있습니다.

```json
{
  "folder_path": "C:/SEM/TestSet_01",
  "label_mapping": {
    "normal": "OK",
    "abnormal": "NG"
  }
}
```

> 이 API는 FastAPI가 이미지 폴더와 같은 로컬 PC에서 실행되는 Windows 데스크톱 구성을 전제로 합니다. 순수 원격 웹 배포에서는 브라우저가 로컬 절대경로를 서버에 직접 노출하지 않으므로 파일 업로드/동기화 계층이 별도로 필요합니다.

### 이미지 목록 조회

큰 Dataset에서 전체 이미지 JSON을 매번 반환하지 않도록 별도 pagination endpoint를 사용합니다.

```http
GET /api/v1/test-datasets/{dataset_id}/images?offset=0&limit=100
GET /api/v1/test-datasets/{dataset_id}/images?ground_truth=NG
GET /api/v1/test-datasets/{dataset_id}/images?unlabeled_only=true
```

### 다중 Ground Truth 변경

```http
PUT /api/v1/test-datasets/{dataset_id}/ground-truth
```

```json
{
  "image_ids": ["...", "...", "..."],
  "ground_truth": "NG",
  "expected_revision": 4
}
```

`ground_truth: null`을 보내면 다시 Unlabeled 상태로 만들 수 있습니다.

## 2. Evaluation 실행

```http
POST /api/v1/evaluations
```

```json
{
  "dataset_id": "sem_bridge_validation_01",
  "recipe_name": "rule_branch_binary_score",
  "image_input_name": "image",
  "decision_output": "result",
  "score_output": "score",
  "ok_label": "OK",
  "ng_label": "NG",
  "capture_node_values": true
}
```

기본 Graph Recipe 형식은 다음 output을 권장합니다.

```text
score  : 최종 scalar feature
result : "OK" 또는 "NG"
passed : bool (선택)
```

Graph Recipe는 Evaluation에 사용하려면 실제 `DecisionNode`를 포함해야 합니다.

### Reference/Mask가 필요한 Recipe

모든 이미지에서 공통으로 사용하는 Reference image나 Mask는 `shared_image_inputs`로 전달할 수 있습니다.

```json
{
  "dataset_id": "reference_test",
  "recipe_name": "my_similarity_rule",
  "image_input_name": "image",
  "shared_image_inputs": {
    "reference": "C:/SEM/reference/golden.png",
    "mask": "C:/SEM/reference/roi_mask.png"
  },
  "decision_output": "result",
  "score_output": "score"
}
```

숫자/문자열과 같은 공통 입력은 `constant_inputs`를 사용합니다.

## 3. 성능 지표

NG를 positive class로 계산합니다.

```text
TP = 실제 NG / 예측 NG
TN = 실제 OK / 예측 OK
FP = 실제 OK / 예측 NG  (False NG, 과검)
FN = 실제 NG / 예측 OK  (Missed NG, 미검)
```

기본 결과:

- Confusion Matrix (`tp`, `tn`, `fp`, `fn`)
- Accuracy
- NG Precision
- NG Recall / Detection Rate
- Specificity / OK Pass Rate
- F1
- 실행 성공률
- Mean / Median / P95 / Max 처리시간
- OK Score 통계
- NG Score 통계

분모가 0인 Precision/Recall/Specificity/F1 항목은 억지로 0을 넣지 않고 `null`을 반환합니다.

## 4. 이미지별 결과

각 이미지에는 다음 정보가 저장됩니다.

```json
{
  "image_id": "...",
  "ground_truth": "NG",
  "prediction": "OK",
  "score": 0.621,
  "correct": false,
  "duration_ms": 8.42,
  "feature_values": {
    "area_feature.value": 0.14,
    "edge_feature.value": 0.08,
    "fusion.value": 0.621,
    "decision.passed": true,
    "decision.label": "OK"
  }
}
```

`capture_node_values=true`일 때 Graph/Pipeline intermediate에서 JSON scalar(`int`, `float`, `bool`, `str`)만 저장합니다. 중간 이미지나 큰 ndarray는 EvaluationRun에 저장하지 않으므로 결과 JSON 크기와 메모리 사용량을 제한합니다.

## 5. ERROR 처리

이미지 파일 손상, 경로 유실, Recipe 실행 실패 등은 임의로 OK/NG에 포함하지 않습니다.

```text
Prediction = ERROR
correct    = null
```

Confusion Matrix와 classification metric은 정상 실행된 이미지에 대해서만 계산하고, 별도로 `error_images`, `execution_success_rate`를 제공합니다.

## 6. 오판 필터

```http
# False NG (실제 OK → 예측 NG)
GET /api/v1/evaluations/{id}/results?ground_truth=OK&prediction=NG

# Missed NG (실제 NG → 예측 OK)
GET /api/v1/evaluations/{id}/results?ground_truth=NG&prediction=OK

# 전체 ERROR
GET /api/v1/evaluations/{id}/results?errors_only=true

# 오판 전체
GET /api/v1/evaluations/{id}/results?correct=false
```

모든 결과 조회는 `offset`, `limit` pagination을 지원합니다.

## 7. EvaluationRun snapshot

EvaluationRun은 실행 당시 Dataset과 Recipe 정보를 함께 고정 기록합니다.

```text
Dataset
- dataset_id
- revision
- image_count

Recipe
- name
- kind (linear / graph)
- version
- revision
```

따라서 이후 Dataset의 Ground Truth 또는 Recipe가 수정되어도 "어떤 revision으로 테스트했는지"를 확인할 수 있습니다.

현재 Recipe snapshot은 metadata snapshot입니다. 과거 Recipe 본문 자체를 immutable version archive로 보존하는 기능은 별도 Recipe Version Store 확장 항목입니다.

## 8. 주요 Endpoint

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/v1/test-datasets` | Dataset 요약 목록 |
| POST | `/api/v1/test-datasets` | Dataset 생성 |
| GET | `/api/v1/test-datasets/{id}` | Dataset 요약 조회 |
| PUT | `/api/v1/test-datasets/{id}` | Dataset 정보 수정 |
| DELETE | `/api/v1/test-datasets/{id}` | Dataset 삭제 |
| POST | `/api/v1/test-datasets/{id}/import-folder` | 이미지 폴더 가져오기 |
| GET | `/api/v1/test-datasets/{id}/images` | 이미지 목록/필터/pagination |
| POST | `/api/v1/test-datasets/{id}/images` | 개별 경로 이미지 추가 |
| PUT | `/api/v1/test-datasets/{id}/images/{image_id}` | 이미지 Ground Truth/metadata 수정 |
| DELETE | `/api/v1/test-datasets/{id}/images/{image_id}` | Dataset에서 이미지 제거 |
| PUT | `/api/v1/test-datasets/{id}/ground-truth` | 다중 Ground Truth 변경 |
| GET | `/api/v1/evaluations` | 평가 이력 목록 |
| POST | `/api/v1/evaluations` | Dataset × Recipe 평가 실행/저장 |
| GET | `/api/v1/evaluations/{id}` | 평가 전체 결과 조회 |
| GET | `/api/v1/evaluations/{id}/results` | 이미지별 결과 필터/pagination |
| DELETE | `/api/v1/evaluations/{id}` | 평가 이력 삭제 |
