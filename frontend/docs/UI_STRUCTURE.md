# UI Structure v0.1

## 공통 Layout

```text
AppShell
├─ Sidebar
├─ GlobalHeader
└─ Page
   ├─ PageToolbar
   └─ PageContent
```

## Design System

공통 토큰은 `src/styles/tokens.css`, 공통 UI는 `src/components/ui/index.tsx`에 둔다.

페이지별 CSS 값을 새로 만들기 전에 공통 토큰과 컴포넌트를 우선 재사용한다.

## Recipe Studio

```text
RecipeStudioPage
├─ RecipeToolbar
├─ RecipeExplorer
├─ OperationLibrary
├─ RecipeCanvas
├─ NodeInspector
└─ PreviewPanel
```

실제 Graph Editor 연결 시 `RecipeCanvas` 내부만 `@xyflow/react`로 교체한다. 외부 Layout은 유지한다.

## Image Lab

```text
ImageLabPage
├─ ImageViewer
├─ ExperimentPanel
└─ AnalysisBottom
   ├─ Histogram
   ├─ Statistics
   └─ ImageFeatures
```

## Dataset

```text
DatasetPage
├─ TestDatasetView
│  ├─ DatasetList
│  └─ DatasetImageBrowser
└─ AnnotationView
   ├─ LabelDocumentList
   ├─ AnnotationEditor
   └─ AnnotationInspector
```

## Evaluation

```text
EvaluationPage
├─ ActiveJobs
├─ EvaluationHistory
├─ EvaluationDetail
└─ EvaluationWizard
```

`EvaluationWizard`는 Modal을 재사용하며 Backend v0.6.0의 202 Accepted Job Queue 흐름을 전제로 한다.

## Settings

```text
SettingsPage
├─ General
├─ Runtime
├─ ModelRegistry
└─ Developer
```
