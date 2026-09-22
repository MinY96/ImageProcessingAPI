# TestDataset / Evaluation Job API

`TestDataset`과 `Evaluation`은 Decision까지 포함된 Recipe를 실제 OK/NG 이미지 집합에 적용해 성능을 검증하기 위한 계층입니다.

v0.6.0부터 Evaluation은 **동기 일괄 실행 방식이 아니라 로컬 Job Queue 방식**으로 동작합니다. `POST /evaluations`는 평가가 끝날 때까지 기다리지 않고 Job을 생성한 뒤 즉시 `202 Accepted`를 반환합니다.

```text
Image Folder
   ↓
TestDataset (Ground Truth: OK / NG)
   ↓
Recipe (Decision output 포함)
   ↓
Evaluation Job Queue
   ↓
Worker (기본 1개)
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

Evaluation 결과는 실행 중 일정 간격으로 checkpoint 저장됩니다.

기본값:

```python
evaluation_worker_count = 1
evaluation_checkpoint_interval = 50
```

One-PC 배포에서는 UI/Recipe Studio 반응성을 보호하기 위해 Worker 1개를 기본값으로 권장합니다.

---

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

> 이 API는 FastAPI가 이미지 폴더와 같은 로컬 PC에서 실행되는 Windows 데스크톱 구성을 전제로 합니다. 원격 서버 배포에서는 브라우저의 로컬 경로와 서버 경로가 다르므로 파일 업로드/동기화 계층이 별도로 필요합니다.

### 이미지 목록 조회

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

---

## 2. Evaluation Job 생성

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

정상 등록 시 평가 완료 결과가 아니라 Job 정보가 즉시 반환됩니다.

```http
HTTP/1.1 202 Accepted
```

```json
{
  "evaluation_id": "e0a9...",
  "status": "queued",
  "progress": {
    "total": 1000,
    "processed": 0,
    "percent": 0.0
  },
  "created_at": "2026-09-10T06:30:00Z"
}
```

API submit 단계에서 다음 항목은 동기 검증합니다.

- Dataset 존재 여부
- Label 존재 여부 (`fail_on_unlabeled=true`)
- Recipe 존재 여부
- Decision output / Score output 존재 여부
- Graph Recipe의 Decision Node 존재 여부
- Recipe input binding 정합성

따라서 잘못된 요청은 Queue에 넣지 않고 기존과 동일하게 `404/422`로 반환합니다.

### 권장 Recipe output

```text
score  : 최종 scalar feature
result : "OK" 또는 "NG"
passed : bool (선택)
```

### Reference / Mask 입력

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

---

## 3. Job 상태 / Progress 조회

```http
GET /api/v1/evaluations/{evaluation_id}
```

실행 중 예시:

```json
{
  "evaluation_id": "e0a9...",
  "status": "running",
  "progress": {
    "total": 1000,
    "processed": 437,
    "percent": 43.7
  },
  "summary": null,
  "results": [],
  "failure": null,
  "created_at": "...",
  "started_at": "...",
  "finished_at": null
}
```

`progress`는 Worker 메모리의 live 상태를 사용하므로 checkpoint 간격과 관계없이 갱신됩니다. `results`와 `summary`는 checkpoint 시점 또는 최종 완료 시 영속화됩니다.

지원 상태:

```text
queued
running
completed
failed
cancel_requested
cancelled
```

상태 흐름:

```text
queued ──────────────→ running ──────────────→ completed
  │                      │
  │ cancel               │ cancel
  ▼                      ▼
cancelled          cancel_requested
                         │
                         ▼
                    cancelled

running ── execution error ──→ failed
```

### Frontend 권장 Polling

WebSocket 없이 1~2초 간격 polling이면 충분합니다.

```text
POST /evaluations
      ↓
evaluation_id
      ↓
GET /evaluations/{id}
      ↓
queued / running
      ↓
completed / failed / cancelled
```

---

## 4. Evaluation 취소

```http
POST /api/v1/evaluations/{evaluation_id}/cancel
```

### queued 상태

아직 Worker가 시작하지 않았다면 즉시 `cancelled`가 됩니다.

### running 상태

즉시 강제 thread kill을 하지 않습니다.

```text
현재 이미지 처리
      ↓
cancel_requested 확인
      ↓
다음 이미지 실행 안 함
      ↓
cancelled
```

즉 OpenCV가 현재 이미지 하나를 처리한 뒤 안전하게 중지합니다.

완료/실패/취소된 Job에 다시 cancel을 호출하면 현재 상태를 그대로 반환합니다.

---

## 5. Checkpoint

Worker는 기본적으로 50장마다 부분 결과를 저장합니다.

```text
1 ~ 49       live progress only
50           checkpoint
51 ~ 99      live progress only
100          checkpoint
...
완료          final save
```

설정:

```python
ApiSettings(
    evaluation_checkpoint_interval=50,
)
```

Checkpoint에는 다음 정보가 저장됩니다.

- 현재 status
- progress
- 현재까지의 image result
- 현재까지의 partial summary

따라서 실행 도중 비정상 종료가 발생하더라도 마지막 checkpoint까지의 결과는 파일에 남습니다.

---

## 6. 앱 종료 / 재시작 복구

### queued Job

앱이 종료되기 전에 아직 실행되지 않은 `queued` Job은 다음 시작 시 Queue에 다시 등록됩니다.

### running / cancel_requested Job

프로세스가 종료된 상태에서는 이전 Worker를 복원할 수 없으므로 시작 시 다음 상태로 변경합니다.

```text
running
cancel_requested
      ↓
failed
```

failure 예시:

```json
{
  "code": "application_terminated",
  "message": "Application terminated while evaluation was running. Submit a new evaluation to run it again."
}
```

현재 1차 구현은 자동 Resume을 지원하지 않습니다.

---

## 7. Dataset / Recipe Revision 보호

Job 등록 시 다음 snapshot을 저장합니다.

```text
Dataset
- dataset_id
- revision
- image_count

Recipe
- name
- kind
- version
- revision
```

Worker가 실제 실행을 시작하기 전에 현재 Dataset/Recipe와 비교합니다.

예를 들어 Queue 대기 중 Recipe가 수정되면 기존 Job이 새 Recipe를 조용히 실행하지 않고 `failed` 처리됩니다.

```text
Queued Recipe revision = 4
Current Recipe revision = 5

→ failed
→ 새 Evaluation 제출 필요
```

이 방식으로 평가 결과의 재현성을 보호합니다.

---

## 8. 성능 지표

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

분모가 0인 Precision/Recall/Specificity/F1 항목은 `null`을 반환합니다.

---

## 9. 이미지별 결과

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

`capture_node_values=true`일 때 intermediate에서 JSON scalar(`int`, `float`, `bool`, `str`)만 저장합니다. 중간 이미지나 큰 ndarray는 EvaluationRun에 저장하지 않습니다.

---

## 10. ERROR 처리

이미지 파일 손상, 경로 유실, Recipe 실행 실패 등은 임의로 OK/NG에 포함하지 않습니다.

```text
Prediction = ERROR
correct    = null
```

Confusion Matrix와 classification metric은 정상 실행된 이미지에 대해서만 계산하고, 별도로 `error_images`, `execution_success_rate`를 제공합니다.

Job 자체를 계속 실행할 수 없는 오류는 image-level `ERROR`가 아니라 Job `failed`로 기록합니다.

---

## 11. 오판 필터

```http
# False NG
GET /api/v1/evaluations/{id}/results?ground_truth=OK&prediction=NG

# Missed NG
GET /api/v1/evaluations/{id}/results?ground_truth=NG&prediction=OK

# 전체 ERROR
GET /api/v1/evaluations/{id}/results?errors_only=true

# 오판 전체
GET /api/v1/evaluations/{id}/results?correct=false
```

모든 결과 조회는 `offset`, `limit` pagination을 지원합니다.

실행 중에는 마지막 checkpoint까지 저장된 결과가 반환될 수 있고, 완료 후에는 전체 결과가 반환됩니다.

---

## 12. Evaluation 목록 / 상태 필터

```http
GET /api/v1/evaluations
GET /api/v1/evaluations?dataset_id=sem_bridge_validation_01
GET /api/v1/evaluations?recipe_name=rule_branch_binary_score
GET /api/v1/evaluations?status=running
GET /api/v1/evaluations?status=completed
```

Frontend의 Running / Waiting / History 영역 구성에 사용할 수 있습니다.

---

## 13. 삭제 규칙

```http
DELETE /api/v1/evaluations/{id}
```

다음 active 상태는 바로 삭제할 수 없습니다.

```text
queued
running
cancel_requested
```

먼저 `/cancel`을 호출해야 합니다. Active Job 삭제 시 `409 evaluation_active`를 반환합니다.

다음 상태는 삭제 가능합니다.

```text
completed
failed
cancelled
```

---

## 14. 주요 Endpoint

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
| GET | `/api/v1/evaluations` | Job/평가 이력 목록 및 상태 필터 |
| POST | `/api/v1/evaluations` | Evaluation Job 등록 (`202 Accepted`) |
| POST | `/api/v1/evaluations/{id}/cancel` | queued/running Evaluation 취소 요청 |
| GET | `/api/v1/evaluations/{id}` | 상태/진행률/결과 조회 |
| GET | `/api/v1/evaluations/{id}/results` | 이미지별 결과 필터/pagination |
| DELETE | `/api/v1/evaluations/{id}` | terminal Evaluation 이력 삭제 |
