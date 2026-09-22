# backend 가상환경 생성

python 3.12.x 버전의 가상환경 생성

```bash
py -3.12 -m venv .venv
```

가상환경 활성화

```bash
.venv\Scripts\activate
```

python 패키지(pip, setuptools, wheel) 업데이트

```bash
python -m pip install --upgrade pip setuptools wheel
```

가상환경 내 requirements.txt 패키지 설치 (가상환경 활성화된 상태에서!)

```bash
python -m pip install -r requirements.txt
```

# Image Processing Studio

OpenCV 기반 Image Processing API와 React 기반 Visual Studio UI를 하나의 저장소에서 관리하는 프로젝트입니다.

## Repository structure

```text
ImageProcessingAPI/
├─ backend/      # Python / FastAPI / OpenCV processing engine
├─ frontend/     # React / TypeScript / Vite UI
├─ .gitignore
└─ README.md
```

## Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

Backend 상세 내용은 [`backend/README.md`](backend/README.md)를 참고하세요.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend 상세 내용은 [`frontend/README.md`](frontend/README.md)를 참고하세요.

## Development URLs

```text
Frontend  http://localhost:5173
Backend   http://localhost:8000
Swagger   http://localhost:8000/docs
```

Frontend Vite dev server는 `/api` 요청을 Backend `localhost:8000`으로 proxy합니다.

## Main UI

- Recipe Studio
- Image Lab
- Synthetic NG Generator
- Dataset / Annotation
- Evaluation Job Queue
- Settings / Model Registry