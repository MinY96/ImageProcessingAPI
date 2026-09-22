# Frontend API Integration Status

## Completed

- Backend Evaluation Job Queue restored and routed through FastAPI lifespan/service/routes.
- Recipe Studio is a writable Linear/Graph editor using Recipe / Operation / Workflow APIs, including draft validate/execute and stored Recipe CRUD.
- Image Lab uses Analysis / Operation / Pipeline / Recipe execution APIs.
- Synthetic NG Generator uses all Synthetic API groups: methods, assets, diffusion status/unload, generation.
- Dataset page uses TestDataset APIs and actual Label/Annotation metadata APIs.
- Evaluation page uses async Job Queue create/list/get/cancel/results APIs and polling.
- Settings uses Health and Model Registry APIs.
- Screen mock-data imports have been removed from `src/`.
- Vite development proxy routes `/api`, `/docs`, `/redoc`, `/openapi.json` to FastAPI on port 8000.

## Backend verification

- `python -m pytest -q`: 179 passed.
- Synthetic procedural multipart smoke test: HTTP 200 and JSON candidate image/mask/difference returned.

## Frontend verification

- Project source TypeScript validation completed with temporary module shims because this build environment could not complete npm dependency installation.
- No temporary shim is included in the repository.
- On the development PC, run `npm install` followed by `npm run build` once to verify against the real React/Vite packages.

## Known backend gaps affecting UI

- TestDataset image binary/thumbnail endpoint is not available. Dataset page therefore displays real file metadata instead of fake thumbnails.
- Label `source_uri` image content endpoint is not available. Annotation metadata is API-connected, but visual bbox/polygon canvas editing should be completed after an image-content endpoint is added.
