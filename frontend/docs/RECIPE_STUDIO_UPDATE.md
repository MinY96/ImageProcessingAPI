# Recipe Studio Editor Update

## Goal

Recipe Studio를 단순 Recipe 조회/실행 화면에서 실제 Linear / Graph Recipe 작성 도구로 확장한다.
Frontend는 별도의 변환용 Recipe 포맷을 만들지 않고 Backend의 `PipelineSpec` / `GraphRecipeSpec`을 Draft state로 직접 편집한다.

## Main workflow

```text
Recipe 선택 또는 New Draft
        ↓
Operation / Feature / Operator / ROI / Decision / SubRecipe 추가
        ↓
Canvas / Inspector에서 binding 및 parameter 편집
        ↓
Validate
        ↓
Run Draft
        ↓
Save
```

## Implemented functions

### Recipe lifecycle

- Linear / Graph 신규 Recipe Draft 생성
- Recipe metadata 편집
  - display name
  - description
  - version
  - tags
- Built-in Recipe readonly 처리
- User Recipe Save / Clone / Reload / Delete
- Revision 기반 Update
- Unsaved changes 감지
- Recipe 전환 시 변경사항 확인
- Browser 종료 전 unsaved warning

### Node Library

공통 Library Panel에서 다음 항목을 추가할 수 있다.

- Operation
- Feature
- Scalar Operator
- ROI Crop
- ROI Compose
- Decision
- SubRecipe

Operation은 Backend category 기준으로 그룹화한다.

### Linear Recipe

- Operation Step 추가 / 삭제
- Step 순서 Up / Down
- 이전 Step output 또는 Recipe input만 binding 가능
- 순서 변경 후 invalid forward reference 자동 제거
- Operation parameter 동적 편집
- Step output을 Recipe output으로 노출
- 실제 Pipeline reference 사용
  - `pipeline_input`
  - `step_output`

### Graph Recipe

- React Flow Canvas 사용
- Recipe Input / Graph Node / Recipe Output 시각화
- Typed input/output port 표시
- Canvas edge 연결 시 실제 `node.inputs` 또는 `graph.outputs` 변경
- Edge 삭제 시 실제 binding 제거
- Node drag position은 UI state로 유지
- Node 삭제 시 다른 Node/output의 dangling reference 제거
- 실제 Graph reference 사용
  - `graph_input`
  - `node_output`

### Inspector

선택 대상에 따라 같은 Inspector Panel을 재사용한다.

- Recipe metadata
- Recipe input
- Recipe output
- Linear step
- Graph node
- Library item information

Backend Parameter schema를 기반으로 category / discrete / continuous parameter editor를 공통 사용한다.

### Special Graph nodes

- ROI Crop
  - pixels / relative coordinate mode
  - x / y / width / height
  - clamp
- ROI Compose
- Decision
  - gt / gte / lt / lte / inside_range / outside_range
  - threshold 또는 lower / upper
  - pass / fail label
- Scalar Operator
  - 일반 parameter
  - n-ary scalar input 추가
- SubRecipe
  - Recipe 선택
  - version 표시
  - SubRecipe input/output interface 조회 후 binding

### Validation

- Linear: `POST /api/v1/pipelines/validate`
- Graph: `POST /api/v1/workflow/validate`
- 빈 Step/Node Draft의 기본 사전 검증
- Backend validation error detail 표시

### Draft execution

저장 전에 현재 Draft 그대로 실행한다.

- Linear: `POST /api/v1/pipelines/execute`
- Graph: `POST /api/v1/workflow/execute`

Run Dialog에서 Recipe input별로 다음을 매핑한다.

- image / mask / template → multipart image file
- model → Model Registry entry
- scalar / array / 기타 → JSON value

Option:

- Retain intermediates
- Analyze intermediates

### Result panel

- Output
- Intermediate
- Metrics
- Validation

## Reusable components

```text
src/features/recipe-studio/
├─ editor.ts
├─ LibraryPanel.tsx
├─ StudioCanvas.tsx
├─ InspectorPanel.tsx
├─ ParameterEditor.tsx
└─ RecipeModals.tsx
```

페이지 컴포넌트는 API orchestration과 Draft state를 담당하고, Library / Canvas / Inspector / Parameter / Modal은 독립 컴포넌트로 재사용한다.

## Current limitations / next candidates

- Undo / Redo history
- Keyboard copy / paste / duplicate
- Node multi-select
- Auto layout
- Group / Comment node
- Validation error를 해당 Node/port에 직접 highlight
- ROI 이미지 Canvas drawing
- Recipe Canvas position persistence
- large graph virtualization/performance tuning

## Verification

Backend regression:

```text
python -m pytest -q
179 passed
```

Frontend source syntax transpile:

```text
32 TS/TSX files
Syntax transpile OK
```

이 작업환경의 npm dependency 설치가 완전하지 않아 실제 `npm run build`는 React/D3 type dependency 누락으로 실행되지 않았다.
개발 PC에서는 다음을 실행해 최종 확인한다.

```powershell
cd frontend
npm install
npm run build
npm run dev
```

## v2.1 layout / canvas fix

Recipe Studio v2 초기본에서 일부 viewport에서 발생하던 레이아웃 문제를 수정했다.

- 공통 `Panel`을 flex column 구조로 변경해 `panel-body`가 남은 높이를 정확히 전달하도록 수정
- React Flow Canvas가 실제 panel 높이를 100% 사용하도록 수정
- Recipe 전환 시 React Flow를 recipe 기준으로 재초기화하여 `fitView`가 정상 적용되도록 보강
- 빈 Draft에도 Canvas 안내와 input/node/output count 표시
- Recipes 목록을 독립 스크롤 영역으로 변경
- Node Library 목록을 독립 스크롤 영역으로 변경
- Inspector / Preview 영역의 overflow 처리 통일
- Recipe Studio 전체 content에 vertical scroll fallback 추가
- 작은 높이의 viewport에서는 최소 editor 높이를 유지하고 페이지 스크롤로 하단 Preview 접근 가능

Frontend syntax verification:

```text
32 TS/TSX files
Syntax transpile OK
```
