# Image Processing Studio Frontend v0.1

기능정의서 `Image Processing Studio 프론트엔드 기능정의서 v0.2` 및 Backend `v0.6.0 (Evaluation Job Queue v1)`을 기준으로 만든 1차 React UI 구현입니다.

## 목표

- 화려한 Dashboard가 아닌 산업용/엔지니어링 도구 느낌의 Dark UI
- 전 페이지에서 동일한 Layout, Panel, Table, Form, Button, Badge 디자인 사용
- 화면 코드와 API 호출 코드를 분리
- Mock 데이터로 UI를 먼저 검토한 후 실제 FastAPI 연동 가능
- Recipe Studio를 핵심 작업 화면으로 구성

## 페이지

- `/recipe-studio`
  - Recipe Explorer
  - Operation Library
  - Graph Canvas UI
  - Node Inspector
  - Preview / Intermediate / Analysis / Metrics / Logs 영역
  - New / Clone / Validate / Run / Save / Delete toolbar
- `/image-lab`
  - Image Viewer
  - Image Analysis / Single Operation / Quick Run 영역
  - Histogram / Statistics / Image Feature
- `/datasets`
  - Test Dataset 탭
  - Dataset List / Image Browser / OK-NG Ground Truth
  - Annotation 탭
  - Label Document List / Annotation Editor / Annotation Inspector / Class Summary
- `/evaluations`
  - Running / Queued Job
  - Evaluation History
  - Evaluation Summary / Confusion Matrix
  - New Evaluation Wizard UI
  - Progress / Cancel 상태 표현
- `/settings`
  - General
  - Runtime
  - Model Registry
  - Developer 문서 링크 영역

## 공통 컴포넌트

`src/components/ui/index.tsx`

- `Button`
- `IconButton`
- `Panel`
- `Badge`
- `ProgressBar`
- `SearchInput`
- `Tabs`
- `Field`
- `Kpi`
- `Modal`

`src/components/layout/AppShell.tsx`

- Sidebar
- Global Header
- Backend Connection Indicator
- Routing Outlet

페이지에서 직접 색상이나 UI 규칙을 새로 만들기보다 위 공통 컴포넌트와 `styles/tokens.css`의 Design Token을 우선 사용하도록 설계했습니다.

## API 구조

`src/api` 아래에서 Backend endpoint를 기능군별로 분리했습니다.

- `system.ts`
- `operations.ts`
- `analysis.ts`
- `pipelines.ts`
- `workflow.ts`
- `recipes.ts`
- `models.ts`
- `labels.ts`
- `datasets.ts`
- `evaluations.ts`

Backend URL 기본값:

```text
http://localhost:8000/api/v1
```

`.env`에서 변경할 수 있습니다.

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 실행

```bash
npm install
npm run dev
```

Build:

```bash
npm run build
```

## 현재 범위

이번 버전은 **UI/UX 1차 구현**입니다.

현재 화면 데이터는 `src/mocks/data.ts`를 사용합니다. 실제 API 모듈은 준비되어 있으나 페이지의 Data Fetching은 아직 연결하지 않았습니다.

다음 단계에서 권장하는 순서는 다음과 같습니다.

1. Design/Layout 확정
2. 화면정의서 작성
3. TanStack Query + API 실제 연결
4. Recipe Canvas를 `@xyflow/react` 기반 실제 Node Editor로 교체
5. Image Viewer / ROI / Annotation Canvas 구현
6. Evaluation polling 및 Cancel 연결
7. 공통 Error / Revision Conflict / Unsaved Changes 처리

## Recipe Canvas

현재 Recipe Canvas는 디자인 확인을 위한 lightweight node mock입니다. `@xyflow/react` dependency는 향후 실제 Graph Editor 구현을 위해 package에 포함했습니다.

화면정의서 확정 후 다음 기능을 React Flow 기반으로 연결하는 것을 권장합니다.

- Node drag/drop
- Typed ports
- Edge validation
- Branch / Merge
- ROI Crop / ROI Compose
- Feature / Scalar Operator
- Decision
- SubRecipe
- Undo / Redo
- Fit View / Zoom

## Design 원칙

### Color

Dark Gray를 기본으로 하고 Accent는 선택/실행 상태에만 제한적으로 사용합니다.

- Background: `#0d1117`
- Sidebar: `#11161d`
- Panel: `#151b23`
- Border: `#2a323d`
- Accent: `#4f8cff`
- Success: `#4db782`
- Warning: `#d8a247`
- Danger: `#db6565`

### Layout

- Sidebar는 모든 화면에서 고정
- Header 높이 고정
- Page Toolbar 위치 고정
- Panel Header 규격 통일
- Recipe Studio만 작업 효율을 위해 3-pane + Bottom Preview 적용
- Dataset Annotation은 3-pane Editor 구조 적용

### UX

- 핵심 Action은 페이지 우측 상단
- 조회/검색은 좌측 또는 상단
- 선택한 객체의 상세 설정은 우측
- 처리 결과/로그는 하단 또는 Detail Panel
- 색상만으로 상태를 표현하지 않고 항상 Text Badge 병행
