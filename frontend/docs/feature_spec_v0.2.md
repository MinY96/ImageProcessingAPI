# Image Processing Studio 프론트엔드 기능정의서 v0.2

> 기준 Backend: **Image Processing API v0.6.0 — Evaluation Job Queue v1**  
> Backend HTTP Endpoint: **49개**  
> 목적: Backend에서 제공하는 모든 기능을 React 기반 Frontend에 빠짐없이 매핑하고, 이후 화면정의서 및 구현의 기준으로 사용한다.

---

## 1. 문서 목적

본 문서는 Image Processing Studio의 Frontend 개발을 위한 기능 기준서이다.

현재 Backend가 제공하는 다음 기능을 UI/UX에 모두 연결한다.

- Operation Registry 및 단일 Operation 실행
- Linear Pipeline 조회/검증/실행
- Graph Workflow 구성/검증/실행
- Recipe CRUD / Clone / Execute
- Image Analysis
- Model Registry 조회
- Annotation Label 관리
- TestDataset 및 Ground Truth 관리
- Evaluation Job Queue / Progress / Cancel / Result 분석
- System Health

### 1.1 Backend 주요 현황

- FastAPI Application Version: `0.6.0`
- Operation: **64개**
- Built-in Linear Recipe: **20개**
- Built-in Graph Recipe: **5개**
- Evaluation Worker 기본값: **1개**
- Evaluation Checkpoint 기본값: **50 images**
- HTTP Endpoint: **49개**

---

# 2. 제품 성격 및 UX 방향

본 프로그램은 단순한 API 호출 도구가 아니라 다음 Workflow를 수행하는 **Vision Recipe IDE / Image Processing Workbench**로 정의한다.

```text
Recipe 개발
   ↓
단일 이미지 검증
   ↓
Test Dataset 구축
   ↓
Evaluation 실행
   ↓
False NG / Missed NG 분석
   ↓
Recipe 수정
```

따라서 관리 시스템 형태의 Dashboard보다 작업 화면 중심으로 구성한다.

---

# 3. 최종 Sidebar 구조

```text
IMAGE PROCESSING STUDIO

◆ Recipe Studio

▣ 이미지 실험실

▤ 데이터셋

▥ 평가

──────────────

⚙ 설정
```

### 상단 Global Header

```text
Recipe Studio > wafer_defect_detection

                              ● Connected

                         ?     ⚙
```

`?` 메뉴:

```text
Documentation
API Documentation
About
```

기본 Route:

```text
/
→ /recipe-studio
```

---

# 4. 기존 후보 메뉴 검토

## 4.1 대시보드

### 결정

**1차 Frontend에서는 제거한다.**

### 이유

현재 Backend에는 Dashboard 전용 API가 없으며, 본 프로그램은 관리 시스템보다 실제 Recipe를 만들고 검증하는 작업 도구 성격이 강하다.

프로그램 실행 시 바로 `Recipe Studio`로 진입하는 편이 사용자 동선이 짧다.

향후 다음 요구가 커지면 Overview 화면으로 다시 추가할 수 있다.

- 최근 Recipe
- 최근 Evaluation
- 장시간 실행 Job
- Dataset 현황
- 시스템 상태

---

## 4.2 API 문서

### 결정

**독립 Sidebar 메뉴에서 제거한다.**

FastAPI 기본 기능을 그대로 활용한다.

```text
/docs
/redoc
/openapi.json
```

접근 위치:

```text
Help (?)
 ├─ Swagger UI
 ├─ ReDoc
 └─ OpenAPI Schema
```

또는:

```text
설정 > Developer
```

---

## 4.3 모델

### 결정

**독립 Sidebar 메뉴에서 제거한다.**

현재 Backend Model API는 조회 기능만 제공한다.

```text
GET /api/v1/models
GET /api/v1/models/{model_id}/{version}
```

현재 미지원:

- Model Upload
- Model Create
- Model Update
- Model Delete
- Model Training
- Model Version 등록

따라서 다음 위치에 흡수한다.

1. `Recipe Studio > Node Inspector > Model Selector`
2. `설정 > Model Registry`

향후 Model CRUD/Training API 추가 시 독립 메뉴로 승격한다.

---

# 5. Page 01 — Recipe Studio

## 5.1 목적

Image Processing Recipe를 생성, 수정, 검증, 실행하는 프로그램의 핵심 화면이다.

Linear Pipeline과 Graph Workflow를 하나의 Recipe Studio 경험으로 제공한다.

---

## 5.2 주요 화면 컴포넌트

```text
RecipeStudioPage
│
├─ RecipeToolbar
│   ├─ New
│   ├─ Validate
│   ├─ Run
│   ├─ Save
│   ├─ Clone
│   └─ Delete
│
├─ RecipeExplorer
│
├─ OperationLibrary
│   ├─ Search
│   ├─ Operation Categories
│   ├─ Feature
│   ├─ Scalar Operator
│   ├─ ROI
│   ├─ Decision
│   └─ SubRecipe
│
├─ RecipeCanvas
│   ├─ Linear Mode
│   └─ Graph Mode
│
├─ NodeInspector
│   ├─ ParameterForm
│   ├─ Input Binding
│   ├─ Output Binding
│   └─ Operation Information
│
└─ PreviewPanel
    ├─ Input
    ├─ Intermediate
    ├─ Output
    ├─ Analysis
    ├─ Metrics
    └─ Logs
```

좌측 / 우측 / 하단 Panel은 Collapse 가능하게 구성한다.

---

## 5.3 Recipe 목록 조회

### 기능 ID

`RS-001`

### 기능

Recipe 목록 조회 및 검색.

Filter:

- Source: `builtin / user`
- Kind: `linear / graph`
- Tag
- Search

표시 정보:

- Recipe Name
- Display Name
- Kind
- Version
- Source
- Revision
- Tags
- Modified Date

### API

```http
GET /api/v1/recipes
```

---

## 5.4 Recipe 상세 열기

### 기능 ID

`RS-002`

Recipe 선택 시 전체 Recipe 정의를 불러온다.

### API

```http
GET /api/v1/recipes/{recipe_name}
```

Recipe 종류:

```text
Linear → PipelineSpec
Graph  → GraphRecipeSpec
```

---

## 5.5 신규 Recipe 생성

### 기능 ID

`RS-003`

생성 Form:

```text
Recipe Type
○ Linear
○ Graph

Name
Display Name
Description
Version
Tags
```

### API

```http
POST /api/v1/recipes
```

---

## 5.6 Recipe Clone

### 기능 ID

`RS-004`

Built-in 및 User Recipe를 새로운 User Recipe로 복제한다.

Built-in Recipe는 Readonly이므로 수정 전에 Clone을 유도한다.

```text
Built-in Recipe

Save      Disabled
Delete    Disabled
Clone     Enabled
Run       Enabled
```

### API

```http
POST /api/v1/recipes/{recipe_name}/clone
```

---

## 5.7 Recipe 수정 / 저장

### 기능 ID

`RS-005`

User Recipe 저장.

Revision 기반 Optimistic Lock 적용.

### API

```http
PUT /api/v1/recipes/{recipe_name}
```

Revision 충돌 시:

```text
Recipe has been modified by another change.

[Reload Latest]
[Cancel]
```

---

## 5.8 Recipe 삭제

### 기능 ID

`RS-006`

User Recipe만 삭제 가능.

### API

```http
DELETE /api/v1/recipes/{recipe_name}?expected_revision={revision}
```

---

# 5.9 Operation Library

### 기능 ID

`RS-010`

Backend Operation Registry에서 Operation 목록을 동적으로 생성한다.

### API

```http
GET /api/v1/operations
```

현재 **64 Operation** 지원.

주요 Category:

```text
Annotation
Adjustment
Color
Classification
Compositing
Effects
Threshold
Filtering
Morphology
Gradient
Geometry
Histogram
Contour
Segmentation
Detection
Transform
Feature
Matching
Registration
```

Library 예:

```text
Search Operations...

▼ Threshold
   Global Threshold
   Adaptive Threshold

▼ Filtering
   Gaussian Blur
   Median Blur
   Bilateral Filter
```

---

## 5.10 Operation 상세 조회

### 기능 ID

`RS-011`

Operation 선택 시 다음 metadata를 조회한다.

- Input
- Output
- Parameter
- Constraint
- Description
- Version

### API

```http
GET /api/v1/operations/{operation}
```

---

## 5.11 Dynamic Parameter Inspector

### 기능 ID

`RS-012`

Operation Schema의 ParameterSpec을 기반으로 입력 UI를 자동 생성한다.

예:

```text
Continuous → Number Input / Slider
Discrete   → Integer Input / Stepper
Category   → Select
Boolean    → Switch
```

Frontend에서 Parameter Constraint를 미리 표현하고, 최종 Validation은 Backend 결과를 사용한다.

---

# 5.12 Graph Feature Library

### 기능 ID

`RS-020`

Graph Recipe에서 Image/Mask/Contour 등의 데이터를 Scalar/Profile Feature로 변환한다.

### API

```http
GET /api/v1/workflow/features
```

현재 주요 Feature:

```text
pixel_statistic
profile_feature
contour_feature
image_similarity
mask_similarity
```

---

## 5.13 Scalar Operator Library

### 기능 ID

`RS-021`

Feature 값 사이의 계산을 수행한다.

### API

```http
GET /api/v1/workflow/operators
```

주요 Operator:

```text
add
subtract
multiply
divide
ratio
abs_diff
sum
mean
min
max
weighted_sum
weighted_mean
normalize_range
```

---

## 5.14 Graph Node Library

### 기능 ID

`RS-022`

지원 Node:

```text
Operation
Feature
Scalar Operator
ROI Crop
ROI Compose
Decision
SubRecipe
```

주요 Data Port Type:

```text
image
mask
template
array
contours
metrics
scalar
profile
roi
roi_set
boolean
decision
```

Frontend는 Port Type이 맞지 않는 연결을 기본적으로 차단한다.
Backend Validation은 최종 정합성을 다시 확인한다.

---

## 5.15 ROI Crop

### 기능 ID

`RS-023`

Image에서 하나 이상의 ROI를 생성하여 서로 다른 Branch로 분기한다.

```text
           ┌ ROI Left   → Pipeline A
Image ─────┼ ROI Center → Pipeline B
           └ ROI Right  → Pipeline C
```

Graph Node:

```text
roi_crop
```

---

## 5.16 ROI Compose

### 기능 ID

`RS-024`

분리 처리된 ROI 결과를 원본 좌표 체계에 다시 조합한다.

```text
ROI A ─┐
ROI B ─┼─ ROI Compose → Image
ROI C ─┘
```

---

## 5.17 Decision Node

### 기능 ID

`RS-025`

Scalar Feature를 Rule과 Threshold로 최종 OK/NG Decision으로 변환한다.

예:

```text
score >= 0.75
→ NG

else
→ OK
```

Evaluation Recipe에서는 Decision Output이 핵심 출력으로 사용된다.

---

## 5.18 SubRecipe

### 기능 ID

`RS-026`

Recipe 내부에서 다른 Recipe를 Node로 재사용한다.

지원 구조:

```text
Linear → Linear
Graph  → Linear
Graph  → Graph
```

SubRecipe 선택 시 Recipe 목록 API를 재사용한다.

### API

```http
GET /api/v1/recipes
GET /api/v1/recipes/{recipe_name}
```

---

## 5.19 Linear Recipe Validation

### 기능 ID

`RS-030`

저장 또는 Run 전에 Pipeline 전체를 사전 검증한다.

### API

```http
POST /api/v1/pipelines/validate
```

검증 대상:

- Operation 존재 여부
- Input Binding
- Output Binding
- Parameter
- Cross Parameter
- Data Kind
- Step Reference

---

## 5.20 Graph Recipe Validation

### 기능 ID

`RS-031`

Graph DAG 전체를 검증한다.

### API

```http
POST /api/v1/workflow/validate
```

검증 대상:

- Cycle
- Node
- Port
- Data Type
- Reference
- Execution Order
- Output Binding

---

## 5.21 저장 전 Linear Recipe 실행

### 기능 ID

`RS-032`

아직 저장되지 않은 Canvas의 Linear Pipeline을 즉시 실행한다.

### API

```http
POST /api/v1/pipelines/execute
```

---

## 5.22 저장 전 Graph Recipe 실행

### 기능 ID

`RS-033`

아직 저장되지 않은 Graph Recipe를 실행한다.

### API

```http
POST /api/v1/workflow/execute
```

---

## 5.23 저장 Recipe 실행

### 기능 ID

`RS-034`

저장된 Recipe 실행.

Frontend가 Linear/Graph 실행 Endpoint를 분리할 필요 없이 Recipe API를 사용한다.

### API

```http
POST /api/v1/recipes/{recipe_name}/execute
```

---

## 5.24 Intermediate Result / Analysis

### 기능 ID

`RS-035`

Run Option:

```text
Retain Intermediate    ON/OFF
Analyze Intermediate   ON/OFF
```

Preview Panel:

```text
Input
Intermediate
Output
Analysis
Metrics
Logs
```

예:

```text
1 Input
2 Gray
3 Gaussian Blur
4 Threshold
5 Morphology
6 Contour
7 Decision
```

---

## 5.25 Response Format

### 기능 ID

`RS-036`

지원 Format:

```text
JSON
ZIP
```

실행 Endpoint Query의 `response_format`과 연결한다.

---

## 5.26 Built-in Pipeline Catalog

### 기능 ID

`RS-040`

Backend의 등록 Linear Pipeline Catalog를 조회한다.

### API

```http
GET /api/v1/pipelines
GET /api/v1/pipelines/{pipeline_name}
```

현재 Built-in Linear Recipe: **20개**.

별도 독립 화면보다 Recipe Explorer 및 Image Lab에서 재사용한다.

---

# 6. Page 02 — 이미지 실험실

## 6.1 목적

Recipe를 만들기 전에 Image와 Operation을 빠르게 실험하는 Workbench.

```text
Recipe Studio = 구성 / 개발
Image Lab     = 탐색 / 실험
```

---

## 6.2 주요 컴포넌트

```text
ImageLabPage
│
├─ InputImagePanel
├─ ModeSelector
│   ├─ Image Analysis
│   ├─ Single Operation
│   ├─ Registered Pipeline
│   └─ Recipe Quick Run
│
├─ ParameterPanel
├─ BeforeAfterViewer
└─ AnalysisPanel
    ├─ Metadata
    ├─ Statistics
    ├─ Histogram
    ├─ Profile
    └─ Features
```

---

## 6.3 Image Analysis

### 기능 ID

`IL-001`

이미지 한 장의 통계 및 특성을 분석한다.

### API

```http
POST /api/v1/analysis/image
```

표시 대상:

### Metadata

- Width
- Height
- Channels
- dtype
- bit depth
- pixel count
- aspect ratio
- color space
- decoded size
- source size

### Statistics

- Min
- Max
- Mean
- Median
- STD
- Variance
- Percentile
- Skewness
- Kurtosis

### Histogram

- Gray
- RGB
- HSV

### Image Feature

- Entropy
- RMS Contrast
- Dark Pixel Ratio
- Bright Pixel Ratio
- Laplacian Variance
- Tenengrad
- Edge Density
- Center of Mass
- Colorfulness

### Profile

- X Projection
- Y Projection
- Derivative Profile

---

## 6.4 Single Operation Experiment

### 기능 ID

`IL-010`

Operation 하나를 선택하고 Parameter를 조절하면서 실행한다.

### API

```http
GET  /api/v1/operations
GET  /api/v1/operations/{operation}
POST /api/v1/operations/{operation}/execute
```

UI 예:

```text
Gaussian Blur

Kernel      5
Sigma       1.2

[Run]

Before | After
```

---

## 6.5 Registered Pipeline Quick Run

### 기능 ID

`IL-020`

등록 Pipeline을 Image 한 장에 빠르게 적용한다.

### API

```http
GET  /api/v1/pipelines
GET  /api/v1/pipelines/{pipeline_name}
POST /api/v1/pipelines/{pipeline_name}/execute
```

---

## 6.6 Recipe Quick Run

### 기능 ID

`IL-021`

저장 Recipe를 선택해 Image에 실행한다.

### API

```http
GET  /api/v1/recipes
POST /api/v1/recipes/{recipe_name}/execute
```

Image Lab에서는 Recipe 편집을 수행하지 않는다.

```text
[Open in Recipe Studio]
```

버튼을 통해 편집 화면으로 이동한다.

---

# 7. Page 03 — 데이터셋

Dataset 메뉴 내부를 두 개의 기능으로 분리한다.

```text
[Test Dataset] [Annotation]
```

두 기능은 목적이 다르므로 UI에서도 명확하게 구분한다.

```text
Test Dataset → Evaluation용 OK/NG Ground Truth
Annotation   → BBox/Polygon/Point/Polyline 위치 Label
```

---

# 8. Dataset Tab 01 — Test Dataset

## 8.1 TestDataset 목록

### 기능 ID

`DS-001`

### API

```http
GET /api/v1/test-datasets
```

지원:

- Search

표시:

```text
Dataset
Images
OK
NG
Unlabeled
Revision
Updated
```

---

## 8.2 Dataset 생성

### 기능 ID

`DS-002`

### API

```http
POST /api/v1/test-datasets
```

입력:

- Dataset ID
- Name
- Description

Folder는 Dataset 생성 후 Import 단계에서 지정한다.

---

## 8.3 Dataset 상세

### 기능 ID

`DS-003`

### API

```http
GET /api/v1/test-datasets/{dataset_id}
```

---

## 8.4 Dataset 수정

### 기능 ID

`DS-004`

### API

```http
PUT /api/v1/test-datasets/{dataset_id}
```

Revision 기반 동시 수정 검증을 적용한다.

---

## 8.5 Dataset 삭제

### 기능 ID

`DS-005`

### API

```http
DELETE /api/v1/test-datasets/{dataset_id}?expected_revision={revision}
```

---

## 8.6 Folder Import

### 기능 ID

`DS-010`

### API

```http
POST /api/v1/test-datasets/{dataset_id}/import-folder
```

지원 옵션:

- Folder Path
- Recursive
- Auto Label From Parent
- Label Mapping

기본 폴더 구조:

```text
dataset/
├─ OK/
│  ├─ image001.png
│  └─ image002.png
└─ NG/
   ├─ image101.png
   └─ image102.png
```

자동 Ground Truth:

```text
OK folder → OK
NG folder → NG
그 외      → Unlabeled
```

본 프로젝트는 우선 **One-PC 배포**를 전제로 하므로 Backend가 해당 Local Folder Path를 직접 읽는 구조를 사용한다.

---

## 8.7 이미지 경로 직접 추가

### 기능 ID

`DS-011`

### API

```http
POST /api/v1/test-datasets/{dataset_id}/images
```

현재 API는 이미지 Binary Upload가 아니라 `file_paths`를 Dataset에 등록하는 구조이다.

---

## 8.8 Dataset Image Browser

### 기능 ID

`DS-012`

### API

```http
GET /api/v1/test-datasets/{dataset_id}/images
```

지원 Query:

```text
offset
limit
ground_truth
unlabeled_only
search
```

UI Filter:

```text
Ground Truth
○ All
○ OK
○ NG

□ Unlabeled Only

Search
```

Pagination 지원.

---

## 8.9 이미지 정보 수정

### 기능 ID

`DS-013`

### API

```http
PUT /api/v1/test-datasets/{dataset_id}/images/{image_id}
```

수정:

- Ground Truth
- Tags
- Metadata
- expected_revision

---

## 8.10 Dataset 이미지 삭제

### 기능 ID

`DS-014`

### API

```http
DELETE /api/v1/test-datasets/{dataset_id}/images/{image_id}?expected_revision={revision}
```

실제 원본 이미지 파일 삭제가 아니라 Dataset Record에서 제거하는 기능으로 표현한다.

---

## 8.11 Batch Ground Truth

### 기능 ID

`DS-015`

다중 이미지 선택 후:

```text
Set OK
Set NG
Clear Label
```

### API

```http
PUT /api/v1/test-datasets/{dataset_id}/ground-truth
```

---

# 9. Dataset Tab 02 — Annotation

## 9.1 목적

이미지의 위치 기반 Annotation을 생성 및 관리한다.

지원 Geometry:

```text
Bounding Box
Polygon
Point
Polyline
```

---

## 9.2 Annotation 목록

### 기능 ID

`AN-001`

### API

```http
GET /api/v1/labels
```

지원:

- Class Filter
- Tag Filter
- Search
- Pagination

---

## 9.3 Annotation Class Summary

### 기능 ID

`AN-002`

### API

```http
GET /api/v1/labels/classes
```

표시 예:

```text
scratch     1,250 annotations / 320 images
particle      820 annotations / 210 images
pattern       150 annotations /  80 images
```

---

## 9.4 Label Document 생성

### 기능 ID

`AN-003`

### API

```http
POST /api/v1/labels
```

저장 정보:

- image_id
- image_name
- source_uri
- width
- height
- tags
- metadata
- annotations

---

## 9.5 Label Document 조회

### 기능 ID

`AN-004`

### API

```http
GET /api/v1/labels/{image_id}
```

---

## 9.6 Label Document 전체 수정

### 기능 ID

`AN-005`

### API

```http
PUT /api/v1/labels/{image_id}
```

Revision Conflict를 UI에서 처리한다.

---

## 9.7 Label Document 삭제

### 기능 ID

`AN-006`

### API

```http
DELETE /api/v1/labels/{image_id}
```

---

## 9.8 Annotation 추가

### 기능 ID

`AN-010`

Canvas Tool:

```text
BBox
Polygon
Point
Polyline
```

### API

```http
POST /api/v1/labels/{image_id}/annotations
```

---

## 9.9 Annotation 수정

### 기능 ID

`AN-011`

### API

```http
PUT /api/v1/labels/{image_id}/annotations/{annotation_id}
```

---

## 9.10 Annotation 삭제

### 기능 ID

`AN-012`

### API

```http
DELETE /api/v1/labels/{image_id}/annotations/{annotation_id}
```

---

# 10. Page 04 — 평가

## 10.1 목적

TestDataset과 Decision Recipe를 연결하여 실제 OK/NG 판정 성능을 평가한다.

v0.6.0부터 Evaluation은 **동기 실행이 아닌 Job Queue 구조**로 동작한다.

```text
Test Dataset
     +
Decision Recipe
     ↓
Evaluation Job 생성
     ↓
Queue
     ↓
Worker
     ↓
Progress / Cancel
     ↓
Evaluation Result
```

기본 Worker는 **1개**이며 One-PC 환경에서 Recipe Studio의 Interactive 작업과 장시간 Evaluation을 분리하는 목적이다.

---

## 10.2 주요 컴포넌트

```text
EvaluationPage
│
├─ EvaluationToolbar
│   └─ New Evaluation
│
├─ EvaluationFilter
│   ├─ Dataset
│   ├─ Recipe
│   └─ Status
│
├─ ActiveJobsPanel
│   ├─ QueuedJobCard
│   ├─ RunningJobCard
│   └─ CancelAction
│
├─ EvaluationHistoryTable
│
└─ EvaluationDetail
    ├─ JobStatus
    ├─ Progress
    ├─ Metrics
    ├─ ConfusionMatrix
    ├─ Latency
    ├─ ScoreDistribution
    └─ ResultExplorer
```

---

## 10.3 Evaluation 목록 / Job History

### 기능 ID

`EV-001`

Evaluation 실행 이력과 현재 Job을 같은 목록에서 조회한다.

### API

```http
GET /api/v1/evaluations
```

지원 Filter:

```text
dataset_id
recipe_name
status
```

지원 Status:

```text
queued
running
completed
failed
cancel_requested
cancelled
```

표시 컬럼:

```text
Evaluation ID
Status
Progress
Dataset
Dataset Revision
Recipe
Recipe Version
Recipe Revision
Accuracy
F1
Failure
Created
Started
Finished
```

Active Job은 목록 상단 또는 별도 Active Jobs 영역에서 강조한다.

---

## 10.4 Evaluation 생성 / Queue 등록

### 기능 ID

`EV-002`

### API

```http
POST /api/v1/evaluations
```

Backend v0.6.0에서는 평가 완료까지 기다리지 않고 **HTTP 202 Accepted**를 반환한다.

응답 예:

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

### Evaluation Wizard

#### Step 1 — Dataset

TestDataset 선택.

#### Step 2 — Recipe

Decision Output을 포함하는 Recipe 선택.

#### Step 3 — Input Binding

```text
Image Input
Decision Output
Score Output
```

#### Step 4 — Label Mapping

```text
OK Label
NG Label
```

#### Step 5 — Shared / Constant Inputs

```text
Shared Image Inputs
Constant Inputs
```

예:

```text
reference image
mask
constant threshold
```

#### Step 6 — Execution Options

```text
Capture Node Values
Fail On Unlabeled
```

#### Step 7 — Submit

```text
[Run Evaluation]
      ↓
202 Accepted
      ↓
Queued Job 화면
```

### Submit 단계 Backend Validation

Queue 등록 전에 다음을 검증한다.

- Dataset 존재 여부
- Unlabeled image 여부 (`fail_on_unlabeled=true`)
- Recipe 존재 여부
- Decision Output 존재 여부
- Score Output 존재 여부
- Graph Recipe Decision Node 여부
- Recipe Input Binding

잘못된 요청은 Queue에 등록하지 않고 `404 / 422`로 반환한다.

---

## 10.5 Evaluation 상태 / Progress 조회

### 기능 ID

`EV-003`

### API

```http
GET /api/v1/evaluations/{evaluation_id}
```

실행 중 예:

```text
RUNNING                         43.7%
██████████████░░░░░░░░░░░░░

437 / 1,000 images

Started  15:31:04

[Cancel]
```

Backend Progress:

```text
total
processed
percent
```

Timestamp:

```text
created_at
started_at
finished_at
```

Failure:

```text
failure.code
failure.message
```

### Frontend Polling

1차 Frontend에서는 WebSocket을 사용하지 않고 polling을 사용한다.

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

권장 Interval:

```text
1 ~ 2초
```

> 단, 현재 `GET /evaluations/{id}`는 `results`까지 포함하므로 대규모 Dataset에서는 응답 크기가 증가할 수 있다. `GAP-08` 참고.

---

## 10.6 Job 상태 전이

### 기능 ID

`EV-004`

```text
queued ───────────→ running ───────────→ completed
  │                    │
  │ cancel             │ cancel
  ▼                    ▼
cancelled        cancel_requested
                       │
                       ▼
                  cancelled

running ─ execution error ─→ failed
```

Status Badge 예:

```text
QUEUED            Gray
RUNNING           Blue
COMPLETED         Green
FAILED            Red
CANCEL REQUESTED  Orange
CANCELLED         Muted
```

실제 색상은 화면정의서의 Design Token에서 확정한다.

---

## 10.7 Evaluation Cancel

### 기능 ID

`EV-005`

### API

```http
POST /api/v1/evaluations/{evaluation_id}/cancel
```

### queued

아직 Worker가 실행하지 않은 Job은 즉시 `cancelled` 처리한다.

### running

실행 중인 Thread를 강제 종료하지 않는다.

```text
현재 Image 처리 완료
       ↓
Cancel Requested 확인
       ↓
다음 Image 실행 중단
       ↓
Cancelled
```

UI:

```text
[Cancel Evaluation]
      ↓
Confirm Dialog
      ↓
CANCEL REQUESTED
```

Terminal 상태의 Job에 Cancel을 다시 요청하면 현재 상태를 그대로 표시한다.

---

## 10.8 Evaluation Checkpoint

### 기능 ID

`EV-006`

현재 Backend 기본값:

```text
Checkpoint Interval = 50 images
```

동작:

```text
1~49    live progress
50      checkpoint
51~99   live progress
100     checkpoint
...
완료     final save
```

Checkpoint 저장 대상:

- Status
- Progress
- 현재까지 Result
- 현재까지 Partial Summary

Frontend는 Checkpoint 자체를 별도로 조작하지 않으며 Job Detail의 상태/결과만 표현한다.

---

## 10.9 앱 재시작 Job Recovery

### 기능 ID

`EV-007`

Backend Application 시작 시 Evaluation Job 상태를 복구한다.

### queued Job

```text
queued
  ↓
Application Restart
  ↓
Queue 재등록
```

### running / cancel_requested Job

이전 Worker Thread를 복구할 수 없으므로:

```text
running / cancel_requested
         ↓
Application Restart
         ↓
failed
```

Failure:

```text
code = application_terminated
```

UI에서는 해당 Job을 `Failed`로 표시하고 재실행 버튼을 제공할 수 있다.

```text
[Run Again]
```

`Run Again`은 기존 Evaluation Request 값을 채운 새 Evaluation Wizard를 여는 Frontend 기능으로 정의한다.

---

## 10.10 Dataset / Recipe Revision Snapshot 검증

### 기능 ID

`EV-008`

Evaluation Submit 시 다음 정보가 Snapshot으로 저장된다.

```text
Dataset
- dataset_id
- name
- revision
- image_count

Recipe
- name
- kind
- version
- revision
```

Queue 대기 중 Dataset 또는 Recipe가 변경된 경우 Worker 실행 시 검증 실패로 Job을 `failed` 처리한다.

목적:

```text
사용자가 평가를 요청한 Dataset/Recipe
≠
실제로 평가된 Dataset/Recipe
```

가 되는 문제를 방지한다.

UI에서는 Revision을 Evaluation 상세에서 표시한다.

---

## 10.11 Evaluation Summary

### 기능 ID

`EV-010`

평가 완료 후 Summary를 표시한다.

### API

```http
GET /api/v1/evaluations/{evaluation_id}
```

### Confusion Matrix

```text
TP
TN
FP
FN
```

### Classification Metrics

```text
Accuracy
Precision
Recall
Specificity
F1
```

### Execution

```text
Total Images
Labeled Images
Evaluated Images
Error Images
Execution Success Rate
```

### Latency

```text
Count
Total
Mean
Median
P95
Max
```

### Score Distribution Summary

OK:

```text
Count
Min
Max
Mean
Median
STD
```

NG:

```text
Count
Min
Max
Mean
Median
STD
```

---

## 10.12 Evaluation Result Explorer

### 기능 ID

`EV-011`

### API

```http
GET /api/v1/evaluations/{evaluation_id}/results
```

지원 Query:

```text
offset
limit
prediction
ground_truth
correct
errors_only
```

Prediction:

```text
OK
NG
ERROR
```

Ground Truth:

```text
OK
NG
```

Quick Filter:

```text
[All]
[False NG]
[Missed NG]
[Error]
```

해석:

```text
False NG  = Ground Truth OK / Prediction NG
Missed NG = Ground Truth NG / Prediction OK
Error     = Prediction ERROR
```

결과 표시:

```text
Image
Ground Truth
Prediction
Score
Correct
Latency
Feature Values
Error
```

Pagination 지원.

---

## 10.13 Evaluation 삭제

### 기능 ID

`EV-012`

### API

```http
DELETE /api/v1/evaluations/{evaluation_id}
```

삭제 가능 Status:

```text
completed
failed
cancelled
```

삭제 불가:

```text
queued
running
cancel_requested
```

Active Job 삭제 시 Backend:

```text
HTTP 409
error.code = evaluation_active
```

UI에서는 Active Job의 Delete 버튼을 비활성화하고 Cancel을 먼저 안내한다.

---

# 11. Page 05 — 설정

현재 Backend에는 Runtime Settings CRUD Endpoint가 없다.

따라서 대부분 Frontend Local Setting으로 처리한다.

---

## 11.1 General

### 기능 ID

`SET-001`

Frontend Local Setting:

```text
Theme
Canvas Grid
Auto Fit
Inspector Width
Preview Panel Height
Default Response Format
Evaluation Polling Interval
```

저장 방법:

```text
LocalStorage
또는 Zustand Persist
```

---

## 11.2 Runtime

### 기능 ID

`SET-010`

Backend 연결 상태 표시.

### API

```http
GET /api/v1/health
```

UI:

```text
Backend
● Connected

API URL
http://localhost:8000

Frontend
React

Backend API
v0.6.0
```

> `/health` 응답은 현재 `{ "status": "ok" }`만 제공하므로 Backend Version은 Build 정보 또는 별도 App metadata 방식이 필요할 수 있다.

---

## 11.3 Model Registry

### 기능 ID

`SET-020`

현재 등록된 Model 목록을 Readonly로 조회한다.

### API

```http
GET /api/v1/models
```

상세:

```http
GET /api/v1/models/{model_id}/{version}
```

표시:

- Model ID
- Version
- Algorithm
- Feature Schema
- Labels
- Metadata

현재는 Readonly.

---

## 11.4 Developer

### 기능 ID

`SET-030`

FastAPI 문서 Link 제공.

```text
Swagger UI
ReDoc
OpenAPI JSON
```

Frontend에서 API Documentation 기능을 직접 구현하지 않는다.

---

# 12. 공통 Application 기능

## 12.1 Backend Connection Indicator

### 기능 ID

`APP-001`

```text
● Connected
● Disconnected
```

### API

```http
GET /api/v1/health
```

Global Header에서 사용한다.

---

## 12.2 공통 Error Handling

### 기능 ID

`APP-002`

Backend Error 응답을 공통 Toast / Dialog로 표시한다.

예:

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {}
  }
}
```

Error 유형에 따라:

```text
Validation → Inspector/Form Inline Error
404        → Resource Not Found
409        → Conflict Dialog
500        → Error Toast + Detail
```

---

## 12.3 Revision Conflict

### 기능 ID

`APP-003`

Revision Lock 대상:

```text
Recipe
Label
TestDataset
```

HTTP 409 발생 시:

```text
Resource has changed.
Reload the latest version?

[Reload]
[Cancel]
```

---

## 12.4 Unsaved Changes

### 기능 ID

`APP-004`

Recipe 변경 후 페이지 이동 시:

```text
Unsaved changes exist.

[Save]
[Discard]
[Cancel]
```

Frontend State 기능.

---

## 12.5 Undo / Redo

### 기능 ID

`APP-005`

Recipe Canvas:

```text
Ctrl + Z
Ctrl + Shift + Z
```

Backend API 없음.
Frontend History State로 구현한다.

---

## 12.6 Evaluation Background Indicator

### 기능 ID

`APP-006`

Evaluation이 실행 중일 때 사용자가 다른 Page로 이동해도 Global Header 또는 Sidebar에서 상태를 확인할 수 있게 한다.

예:

```text
▥ 평가   ● 1 Running
```

또는:

```text
Top Bar
Evaluation  437 / 1000 · 43.7%
```

데이터:

```http
GET /api/v1/evaluations?status=running
GET /api/v1/evaluations?status=queued
```

1차 버전에서는 단순 Badge만 지원하고 상세 Progress는 Evaluation Page에서 확인한다.

---

# 13. API 전체 Coverage Matrix

현재 Backend HTTP API **49 / 49 매핑**.

| No. | API 영역 | Method | Endpoint | Frontend 매핑 |
|---:|---|---|---|---|
| 1 | System | GET | `/api/v1/health` | Global Header / Settings |
| 2 | Operation | GET | `/api/v1/operations` | Recipe Studio / Image Lab |
| 3 | Operation | GET | `/api/v1/operations/{operation}` | Node Inspector / Image Lab |
| 4 | Operation | POST | `/api/v1/operations/{operation}/execute` | Image Lab |
| 5 | Model | GET | `/api/v1/models` | Settings / Model Selector |
| 6 | Model | GET | `/api/v1/models/{model_id}/{version}` | Settings / Node Inspector |
| 7 | Analysis | POST | `/api/v1/analysis/image` | Image Lab |
| 8 | Pipeline | GET | `/api/v1/pipelines` | Recipe Studio / Image Lab |
| 9 | Pipeline | GET | `/api/v1/pipelines/{pipeline_name}` | Recipe Studio / Image Lab |
| 10 | Pipeline | POST | `/api/v1/pipelines/validate` | Recipe Studio |
| 11 | Pipeline | POST | `/api/v1/pipelines/execute` | Recipe Studio |
| 12 | Pipeline | POST | `/api/v1/pipelines/{pipeline_name}/execute` | Image Lab |
| 13 | Workflow | GET | `/api/v1/workflow/features` | Recipe Studio |
| 14 | Workflow | GET | `/api/v1/workflow/operators` | Recipe Studio |
| 15 | Workflow | POST | `/api/v1/workflow/validate` | Recipe Studio |
| 16 | Workflow | POST | `/api/v1/workflow/execute` | Recipe Studio |
| 17 | Recipe | GET | `/api/v1/recipes` | Recipe Studio / Image Lab / Evaluation |
| 18 | Recipe | POST | `/api/v1/recipes` | Recipe Studio |
| 19 | Recipe | POST | `/api/v1/recipes/{recipe_name}/clone` | Recipe Studio |
| 20 | Recipe | GET | `/api/v1/recipes/{recipe_name}` | Recipe Studio |
| 21 | Recipe | PUT | `/api/v1/recipes/{recipe_name}` | Recipe Studio |
| 22 | Recipe | DELETE | `/api/v1/recipes/{recipe_name}` | Recipe Studio |
| 23 | Recipe | POST | `/api/v1/recipes/{recipe_name}/execute` | Recipe Studio / Image Lab |
| 24 | Label | GET | `/api/v1/labels` | Dataset > Annotation |
| 25 | Label | POST | `/api/v1/labels` | Dataset > Annotation |
| 26 | Label | GET | `/api/v1/labels/classes` | Dataset > Annotation |
| 27 | Label | GET | `/api/v1/labels/{image_id}` | Annotation Editor |
| 28 | Label | PUT | `/api/v1/labels/{image_id}` | Annotation Editor |
| 29 | Label | DELETE | `/api/v1/labels/{image_id}` | Annotation Editor |
| 30 | Label | POST | `/api/v1/labels/{image_id}/annotations` | Annotation Editor |
| 31 | Label | PUT | `/api/v1/labels/{image_id}/annotations/{annotation_id}` | Annotation Editor |
| 32 | Label | DELETE | `/api/v1/labels/{image_id}/annotations/{annotation_id}` | Annotation Editor |
| 33 | Dataset | GET | `/api/v1/test-datasets` | Dataset |
| 34 | Dataset | POST | `/api/v1/test-datasets` | Dataset |
| 35 | Dataset | GET | `/api/v1/test-datasets/{dataset_id}` | Dataset |
| 36 | Dataset | PUT | `/api/v1/test-datasets/{dataset_id}` | Dataset |
| 37 | Dataset | DELETE | `/api/v1/test-datasets/{dataset_id}` | Dataset |
| 38 | Dataset | POST | `/api/v1/test-datasets/{dataset_id}/import-folder` | Dataset |
| 39 | Dataset | GET | `/api/v1/test-datasets/{dataset_id}/images` | Dataset Image Browser |
| 40 | Dataset | POST | `/api/v1/test-datasets/{dataset_id}/images` | Dataset |
| 41 | Dataset | PUT | `/api/v1/test-datasets/{dataset_id}/images/{image_id}` | Dataset Image Browser |
| 42 | Dataset | DELETE | `/api/v1/test-datasets/{dataset_id}/images/{image_id}` | Dataset Image Browser |
| 43 | Dataset | PUT | `/api/v1/test-datasets/{dataset_id}/ground-truth` | Dataset Image Browser |
| 44 | Evaluation | GET | `/api/v1/evaluations` | Evaluation Queue / History |
| 45 | Evaluation | POST | `/api/v1/evaluations` | Evaluation Wizard / Queue Submit |
| 46 | Evaluation | POST | `/api/v1/evaluations/{evaluation_id}/cancel` | Evaluation Active Job |
| 47 | Evaluation | GET | `/api/v1/evaluations/{evaluation_id}` | Evaluation Job Detail / Progress / Summary |
| 48 | Evaluation | DELETE | `/api/v1/evaluations/{evaluation_id}` | Evaluation History |
| 49 | Evaluation | GET | `/api/v1/evaluations/{evaluation_id}/results` | Evaluation Result Explorer |

**Coverage: 49 / 49 (100%)**

---

# 14. 페이지별 API Coverage 요약

| Page | API 수용 영역 |
|---|---|
| Recipe Studio | Operations, Pipelines, Workflow, Recipes, Models 일부 |
| 이미지 실험실 | Analysis, Operations 실행, Pipeline 실행, Recipe 실행 |
| 데이터셋 | TestDataset, Labels/Annotations |
| 평가 | Evaluation Job Queue, Progress, Cancel, Summary, Results |
| 설정 | Health, Model Registry, API Documentation 링크 |

---

# 15. 핵심 사용자 Workflow

## 15.1 Recipe 개발

```text
Recipe Studio
    ↓
New Recipe
    ↓
Operation Drag & Drop
    ↓
Parameter 설정
    ↓
ROI / Branch / Feature
    ↓
Scalar Operator
    ↓
Decision
    ↓
Validate
    ↓
Single Image Run
    ↓
Save
```

---

## 15.2 이미지 실험

```text
Image Lab
   ↓
Image Load
   ↓
Analysis / Operation / Pipeline / Recipe
   ↓
Before & After 비교
   ↓
필요 시 Recipe Studio로 이동
```

---

## 15.3 Dataset 구축

```text
Dataset
   ↓
Create Test Dataset
   ↓
Import OK/NG Folder
   ↓
Ground Truth 확인
   ↓
수동 수정 / Batch Label
```

---

## 15.4 Evaluation 실행

```text
Evaluation
   ↓
Dataset 선택
   ↓
Recipe 선택
   ↓
Input / Output Binding
   ↓
Run Evaluation
   ↓
202 Accepted
   ↓
Queued
   ↓
Running + Progress
   ↓
Completed
```

사용자는 Evaluation 실행 중 Recipe Studio 또는 다른 Page로 이동할 수 있다.

---

## 15.5 Evaluation 개선 Loop

```text
Evaluation Result
      ↓
False NG / Missed NG 확인
      ↓
Feature Value / Score 분석
      ↓
Recipe Studio
      ↓
Parameter / Pipeline 수정
      ↓
Save New Revision
      ↓
Evaluation 재실행
```

본 Workflow가 프로그램의 가장 중요한 반복 사용 흐름이다.

---

# 16. Frontend Route 초안

```text
/

/recipe-studio
/recipe-studio/:recipeName

/image-lab

/datasets
/datasets/test
/datasets/test/:datasetId

/datasets/annotations
/datasets/annotations/:imageId

/evaluations
/evaluations/:evaluationId

/settings
/settings/general
/settings/runtime
/settings/models
/settings/developer
```

기본 Redirect:

```text
/
→ /recipe-studio
```

---

# 17. Backend / Frontend Gap 및 향후 개선사항

## GAP-01 — TestDataset Image Preview API 없음

현재 TestDataset Image API는 `file_path` 정보를 제공하지만 Browser에서 해당 Local File을 직접 이미지로 표시할 수 있는 Content API는 없다.

필요 후보:

```http
GET /api/v1/test-datasets/{dataset_id}/images/{image_id}/content
```

또는 Thumbnail 전용:

```http
GET /api/v1/test-datasets/{dataset_id}/images/{image_id}/thumbnail
```

### 필요 화면

- Dataset Image Browser
- Evaluation Result Explorer

### 우선순위

**높음**

---

## GAP-02 — Folder Import는 Local Backend Path 기준

현재 Folder Import는 Backend가 접근 가능한 `folder_path`를 받는다.

```http
POST /api/v1/test-datasets/{dataset_id}/import-folder
```

현재 배포 방향이 **Frontend + Backend One-PC**이므로 1차 제품에서는 적합하다.

단, 향후 원격 중앙 Server 방식으로 바뀌면 Browser Local Folder와 Server Folder가 다르므로 Upload/Sync 기능이 필요하다.

### 현재 우선순위

**낮음 — One-PC 전제에서 허용**

---

## GAP-03 — Annotation 원본 이미지 제공 경로

Label API는 `source_uri`와 Annotation metadata를 저장하지만 원본 Image Content 제공 Endpoint는 없다.

Annotation Editor에서 Label을 다시 열 때 Browser가 원본 이미지를 읽을 수 있어야 한다.

후보:

```http
GET /api/v1/labels/{image_id}/content
```

또는 공통 Media API 도입.

### 우선순위

**높음**

---

## GAP-04 — Evaluation 동기 실행 문제

### 상태

**해결 완료 — v0.6.0**

기존:

```text
POST /evaluations
→ 전체 평가 완료 후 Response
```

현재:

```text
POST /evaluations
→ 202 Accepted
→ Local Queue
→ Worker
→ Progress / Cancel
```

---

## GAP-05 — Model 관리 기능 없음

현재 Model Registry는 Readonly 조회만 제공한다.

따라서 1차 Frontend에서는 `Model Registry Viewer`로 정의한다.

향후 후보:

```text
Model 등록
Model 삭제
Model Version 관리
ONNX/PyTorch Import
Training
```

### 우선순위

**낮음 — 현재 Scope 외**

---

## GAP-06 — Backend Settings API 없음

다음 Backend 설정은 현재 코드 설정으로만 존재한다.

예:

```text
evaluation_worker_count
evaluation_checkpoint_interval
max_test_dataset_images
max_upload_files
max_image_pixels
max_total_decoded_bytes
```

Frontend에서 Runtime 변경 API는 없다.

1차 버전에서는 고정 설정을 사용하고 필요 시 설정 파일 방식으로 관리한다.

### 우선순위

**낮음**

---

## GAP-07 — Publish API 없음

초기 UI 디자인에 있던 `Publish` 버튼에 대응하는 Backend 기능은 현재 없다.

따라서 1차 Recipe Toolbar에서는 제거한다.

```text
New
Validate
Run
Save
Clone
Delete
```

향후 Recipe 승인/배포 체계가 필요해지면 별도 기능으로 정의한다.

---

## GAP-08 — Evaluation Polling 응답 경량화 필요

현재:

```http
GET /api/v1/evaluations/{evaluation_id}
```

은 다음을 모두 포함하는 `EvaluationRun`을 반환한다.

```text
status
progress
summary
results
failure
...
```

Evaluation Result가 수천~수만 건으로 증가하면 Frontend가 1~2초 Polling할 때 매번 큰 `results` 배열을 전달할 수 있다.

### 권장 Backend 보완

가벼운 Job Status Endpoint를 추가하는 것이 좋다.

후보 A:

```http
GET /api/v1/evaluations/{evaluation_id}/status
```

응답:

```json
{
  "evaluation_id": "...",
  "status": "running",
  "progress": {
    "total": 1000,
    "processed": 437,
    "percent": 43.7
  },
  "failure": null,
  "created_at": "...",
  "started_at": "...",
  "finished_at": null
}
```

후보 B:

기존 상세 API에 Query 추가:

```http
GET /api/v1/evaluations/{evaluation_id}?include_results=false
```

### 권장

**후보 A `/status` Endpoint 분리**가 역할이 명확해 Frontend Query 관리에 유리하다.

### 우선순위

**높음 — Frontend Evaluation 구현 전 보완 권장**

---

## GAP-09 — Evaluation Resume 미지원

현재 Application 재시작 시:

```text
queued → Queue 복원
running → failed
cancel_requested → failed
```

마지막 Checkpoint부터 Resume하는 기능은 없다.

One-PC 1차 버전에서는 현재 동작으로 충분하며, 대규모 Evaluation 운영 시 향후 검토한다.

### 우선순위

**낮음**

---

## GAP-10 — Queue Position 정보 없음

현재 Backend는 Job `queued` 여부를 제공하지만 정확한 Queue Position을 API로 반환하지 않는다.

따라서 Frontend 1차 버전에서는:

```text
Queued
```

만 표시하고:

```text
2nd in Queue
```

같은 정확한 순번은 표시하지 않는다.

필요 시 향후 Queue metadata를 확장한다.

### 우선순위

**낮음**

---

# 18. One-PC 배포 기준 기능 설계 원칙

현재 제품의 1차 배포 방향은 Frontend와 Backend를 동일 PC에서 실행하는 형태로 정의한다.

```text
Windows PC
│
├─ React Frontend
│
├─ FastAPI Backend
│   ├─ Interactive Operation / Recipe Execution
│   └─ Evaluation Queue Worker = 1
│
├─ Local Image Folder
│
└─ .image_processing_data
    ├─ recipes
    ├─ labels
    ├─ test_datasets
    └─ evaluations
```

설계 원칙:

1. Recipe Studio의 Interactive Run 반응성을 우선한다.
2. 무거운 Evaluation은 Queue Worker에서 처리한다.
3. Worker 기본값은 1개를 유지한다.
4. Evaluation 실행 중에도 다른 UI 작업이 가능해야 한다.
5. Frontend 종료/페이지 이동이 Evaluation Job 중단을 의미하지 않는다.
6. Backend 재시작 시 Queued Job은 복구하고 실행 중 Job은 명시적으로 Failed 처리한다.

---

# 19. 화면정의서 작성 시 우선 대상

본 기능정의서를 기준으로 다음 순서로 화면정의서를 작성한다.

```text
1. Global Layout / Navigation

2. Recipe Studio
   - 핵심 작업 화면
   - React Flow 기반 Canvas

3. 이미지 실험실

4. Test Dataset

5. Evaluation
   - Queue
   - Progress
   - Result

6. Annotation Editor

7. Settings
```

특히 Recipe Studio와 Evaluation은 서로 반복 이동하는 핵심 화면이므로 동일한 Design Language와 빠른 Navigation을 적용한다.

---

# 20. 최종 기능 영역 요약

```text
Recipe Studio
→ 만든다.

Image Lab
→ 시험한다.

Dataset
→ 정답 데이터를 만든다.

Evaluation
→ 성능을 검증한다.

Settings
→ 실행 환경과 Backend Resource를 확인한다.
```

최종 핵심 Loop:

```text
BUILD
Recipe Studio
      ↓
TEST
Image Lab
      ↓
DATA
Test Dataset
      ↓
EVALUATE
Evaluation Queue
      ↓
ANALYZE
False NG / Missed NG
      ↓
IMPROVE
Recipe Studio
```

---

# 21. 버전 변경 이력

## v0.2 — Backend v0.6.0 대응

- Backend Endpoint `48 → 49` 반영
- `POST /evaluations` 동기 실행 → `202 Accepted` Job Queue 방식으로 수정
- Evaluation 상태 `queued/running/completed/failed/cancel_requested/cancelled` 반영
- Progress UI 및 Polling Workflow 추가
- `POST /evaluations/{id}/cancel` 신규 Endpoint 매핑
- Active Evaluation 삭제 제한 반영
- Evaluation Checkpoint 기능 반영
- Application Restart Recovery 정책 반영
- Dataset/Recipe Revision Snapshot 검증 반영
- Global Evaluation Background Indicator 추가
- One-PC 배포 원칙 추가
- 기존 Evaluation 동기 실행 Gap을 해결 완료로 변경
- Evaluation polling payload 경량화 필요사항(`GAP-08`) 신규 등록

## v0.1

- Backend v0.5.0 기준 최초 작성
- Recipe Studio / Image Lab / Dataset / Evaluation / Settings 구조 정의
- Backend API 48개 매핑
