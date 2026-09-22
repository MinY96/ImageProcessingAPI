# Image Processing Studio Frontend

React + TypeScript + Vite 기반 Image Processing Studio 프론트엔드입니다.
현재 소스는 Backend v0.6.0 계열의 실제 API에 연결되어 있으며, 화면용 Mock dataset을 사용하지 않습니다.

## 기술 스택

- React 19
- TypeScript 5.8
- Vite 7
- React Router
- `@xyflow/react` (Recipe Graph 표시/확장 기반)

## 페이지

- `/recipe-studio`
  - 실제 Recipe / Operation / Workflow Feature / Scalar Operator 조회
  - Linear / Graph Recipe 구조 Canvas 표시
  - Recipe Validate / Run / Clone / Save / Delete
  - 실제 Output / Intermediate image 표시
- `/image-lab`
  - 이미지 업로드
  - Image Analysis
  - Single Operation 실행
  - Built-in Pipeline / User Recipe Quick Run
  - 실제 Histogram / Statistics / Feature 결과 표시
- `/synthetic-ng`
  - Synthetic method 조회
  - Procedural / CutPaste / Alpha Blend / Seamless Clone / Asset Composite / Diffusion Inpaint 실행
  - Manual / Rectangle / Ellipse / Polygon / Random Blob / Perlin / Crack mask
  - Synthetic Asset 등록/조회/삭제
  - Diffusion runtime 상태 조회 및 unload
  - Generated / Mask / Difference / Quality metric 결과 확인
- `/datasets`
  - Test Dataset CRUD 및 Folder Import
  - OK / NG / Unlabeled Ground Truth 관리
  - Batch Ground Truth 수정
  - Label Document / Annotation metadata 조회 및 관리
- `/evaluations`
  - Evaluation Job Queue 이력
  - `queued / running / completed / failed / cancel_requested / cancelled`
  - 진행률 Polling
  - Running Job Cancel
  - Confusion Matrix / metric / latency / 이미지별 결과 조회
- `/settings`
  - Local UI setting
  - Backend Health
  - Model Registry
  - Swagger / ReDoc / OpenAPI 링크

## 개발 환경

권장:

- Node.js 24 LTS
- npm 11+
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

## 설치

```powershell
cd frontend
npm install
```

## 실행

Backend를 먼저 실행합니다.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

프로젝트에서 사용하는 실제 실행 entrypoint가 별도라면 기존 backend 실행 명령을 그대로 사용해도 됩니다.

다른 VS Code Terminal에서 Frontend를 실행합니다.

```powershell
cd frontend
npm run dev
```

브라우저:

```text
http://localhost:5173
```

## Backend 연결

기본 API base URL은 상대경로입니다.

```text
/api/v1
```

개발 중에는 `vite.config.ts`가 다음 요청을 FastAPI로 proxy합니다.

```text
/api/*       -> http://localhost:8000
/docs        -> http://localhost:8000
/redoc       -> http://localhost:8000
/openapi.json -> http://localhost:8000
```

따라서 개발환경에서 별도의 CORS 설정 없이 Frontend와 Backend를 함께 실행할 수 있습니다.

필요하면 `.env`에서 변경할 수 있습니다.

```env
VITE_API_BASE_URL=/api/v1
```

`.env.example`은 Git에 포함하고 실제 `.env*`는 저장소에서 제외하는 방식을 권장합니다.

## Production build

```powershell
npm run build
```

성공하면 `frontend/dist/`가 생성됩니다.

One-PC 배포에서는 최종적으로 이 `dist/`를 FastAPI가 정적 파일로 제공하게 구성할 수 있습니다.

## API 계층

`src/api/`에서 화면과 HTTP 호출을 분리합니다.

```text
src/api/
├─ client.ts
├─ system.ts
├─ operations.ts
├─ analysis.ts
├─ pipelines.ts
├─ workflow.ts
├─ recipes.ts
├─ models.ts
├─ labels.ts
├─ datasets.ts
├─ evaluations.ts
└─ synthetic.ts
```

새 화면에서도 `fetch()`를 직접 호출하기보다 위 API module을 재사용하는 것을 원칙으로 합니다.

## 공통 컴포넌트

`src/components/ui/index.tsx`

- Button / IconButton
- Panel
- Badge
- ProgressBar
- SearchInput
- Tabs
- Field
- Kpi
- Modal
- EmptyState
- InlineError
- Loading

색상/간격은 `src/styles/tokens.css`를 기준으로 통일합니다.

## 현재 제한사항

### Dataset thumbnail

TestDataset API는 이미지 경로/metadata는 반환하지만 image binary/thumbnail endpoint는 아직 제공하지 않습니다.
따라서 Dataset 화면에서는 가짜 thumbnail을 만들지 않고 실제 file metadata를 표시합니다.

### Annotation canvas

Label API는 annotation CRUD를 지원하지만 `source_uri`의 원본 이미지를 Browser에 전달하는 content API가 아직 없습니다.
현재 화면은 실제 Label/Annotation metadata를 조회하며, Canvas 기반 bbox/polygon 편집기는 image content endpoint 추가 후 연결하는 것이 적절합니다.

### Recipe editor

현재 Recipe Studio Canvas는 실제 Recipe 구조를 조회해 표시하고 실행/검증 API와 연결되어 있습니다.
노드 Drag & Drop, typed edge editing, ROI canvas, Undo/Redo 등 완전한 Visual Recipe Authoring 기능은 다음 단계 확장 항목입니다.

## Evaluation Job Queue

Backend의 Evaluation은 비동기 Job Queue 방식입니다.
Frontend는 약 2초 간격으로 Evaluation 목록/상태를 갱신하며 Running Job을 취소할 수 있습니다.

```text
POST /api/v1/evaluations
        ↓ 202 Accepted
queued
        ↓
running
        ↓
completed / failed / cancelled
```

## Synthetic NG

Synthetic NG API 문서는 Backend의 다음 파일을 참고합니다.

```text
backend/docs/synthetic_ng_api.md
```

Diffusion Inpainting은 Backend 환경에 해당 optional dependency와 로컬 model이 준비되어 있어야 실행됩니다.
