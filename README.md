# Paper Checker

Paper Checker is a web application for collecting exam answer keys and student papers, extracting answers with AI, grading objective and written responses, and reviewing results in a dashboard.

The project has two parts:

- `backend/`: FastAPI API, MongoDB persistence, document processing, and AI grading
- `frontend/`: Angular 21 user interface for answer keys, submissions, batches, and reports

## Features

- Create answer keys manually or upload PDF/image files for AI extraction
- Extract multiple-choice and free-text questions from scanned documents
- Upload scanned student answer sheets or enter responses manually
- Match extracted responses to answer-key questions
- Grade MCQs locally
- Grade written answers using rubric criteria and semantic-similarity fallback
- Create batches of submissions and view batch results
- Export submission results as CSV
- Confirm reviewed grading reports
- Use Gemini vision and configurable text LLM providers with fallback and retry handling
- Protect write endpoints with an optional `X-API-Key` header
- Enforce configurable model request limits of 15 requests/minute and 500 requests/day by default

## Architecture

```text
Angular frontend
        |
        | HTTP
        v
FastAPI backend ---- MongoDB
        |
        +---- Gemini Vision: scanned answer-key and submission extraction
        |
        +---- Groq/Gemini text LLMs: written-answer rubric grading
        |
        +---- Local MCQ comparison and embedding similarity fallback
```

Uploaded PDFs are rendered page by page with PyMuPDF before being sent to a vision model. The backend stores answer keys, submissions, batches, and grade results in MongoDB.

## Requirements

- Windows, macOS, or Linux
- Python 3.12+
- Node.js and npm
- MongoDB, local or hosted
- API credentials for at least one configured model provider

## Local Setup

### 1. Clone and enter the project

```bash
git clone <repository-url>
cd paper-checker
```

### 2. Configure the backend

Create `backend/.env`:

```dotenv
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=paper_checker

# At least one text provider is required for written-answer grading.
GROQ_API_KEYS=your-groq-key
GROQ_MODELS=openai/gpt-oss-120b,openai/gpt-oss-20b

# Gemini is required for PDF/image extraction.
GEMINI_API_KEYS=your-gemini-key
GEMINI_MODELS=gemini-2.5-flash,gemini-2.0-flash-lite

# Optional API protection. Leave empty for local development.
API_KEY=

# Shared process-local model request budget.
MODEL_REQUESTS_PER_MINUTE=15
MODEL_REQUESTS_PER_DAY=500

# Frontend origins allowed by the backend.
CORS_ORIGINS=http://localhost:4200
```

Never commit `.env` files or API keys.

### 3. Install and run the backend

From the repository root on Windows PowerShell:

```powershell
py -3.12 -m venv myvenv
.\myvenv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

The API is available at `http://localhost:8000`.

Useful URLs:

- Health check: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

If MongoDB is not running, the backend lifespan will fail during startup.

### 4. Install and run the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm start
```

Open `http://localhost:4200`.

The development Angular environment uses `http://localhost:8000` as its API base URL. The production environment currently points to the deployed API configured in `frontend/src/environments/environment.ts`.

## Main API Routes

All routes are prefixed from the root URL. Write operations require `X-API-Key` when `API_KEY` is configured.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check API health |
| `GET` | `/answer-keys` | List answer keys |
| `POST` | `/answer-keys` | Create a typed answer key |
| `POST` | `/answer-keys/upload` | Extract an answer key from PDF/image/DOCX input |
| `GET` | `/answer-keys/{id}` | Get one answer key |
| `PUT` | `/answer-keys/{id}` | Update an answer key |
| `DELETE` | `/answer-keys/{id}` | Delete an answer key and related data |
| `POST` | `/submissions/upload` | Extract a scanned student submission |
| `POST` | `/submissions` | Create a submission manually |
| `GET` | `/submissions` | List submissions |
| `POST` | `/batches` | Create a submission batch |
| `GET` | `/batches/{id}` | View batch results |
| `GET` | `/batches/{id}/csv` | Export batch results |
| `POST` | `/grading/{submission_id}` | Grade a submission |
| `GET` | `/reports/{submission_id}` | Get a grading report |
| `PATCH` | `/reports/{submission_id}/confirm` | Confirm a reviewed report |

Interactive API documentation is available at `/docs` while the backend is running.

## Grading Flow

1. A teacher creates or uploads an answer key.
2. The backend extracts question text, MCQ options, reference answers, and rubrics.
3. A student paper is uploaded or entered manually.
4. The backend extracts MCQ selections, written responses, and roll number when available.
5. MCQs are checked locally against the answer key.
6. Written responses are graded together in a rubric request. If the text provider is unavailable, semantic similarity is used as a fallback.
7. The result is stored and displayed as a report.
8. The teacher can confirm the report or export batch results.

## API Usage Limits

The default model budget is:

- 15 outbound model requests per rolling minute
- 500 outbound model requests per rolling 24-hour window

The budget counts successful calls, failed calls, provider fallbacks, and retries. It is process-local, so multiple backend workers do not share one global counter.

For a paper containing MCQ and text answers:

- 1 request extracts the student submission
- 1 request grades all written answers together
- MCQ grading uses no model request

After one answer-key extraction request, the theoretical daily capacity is:

```text
floor((500 - 1) / 2) = 249 papers per day
```

Retries and re-grading reduce that practical capacity. The RPM limit means about 7 such papers can begin per minute before requests wait in the limiter.

## Testing

### Backend

From `backend/` with the project virtual environment active:

```powershell
python -m pytest -q
```

The backend test suite covers extraction helpers, JSON parsing, MCQ grading, written-answer grading, provider fallback/retry behavior, and API budget behavior.

### Frontend

From `frontend/`:

```powershell
npm test
```

Build the production frontend with:

```powershell
npm run build
```

## Deployment

### Backend on Render

The root `render.yaml` defines a Docker web service named `paper-checker-backend`.

Configure these Render environment variables:

- `MONGODB_URL`
- `MONGODB_DB_NAME`
- `GROQ_API_KEYS` and `GROQ_MODELS`
- `GEMINI_API_KEYS` and `GEMINI_MODELS`
- `API_KEY`, if endpoint protection is required
- `CORS_ORIGINS` with the deployed frontend origin
- `MODEL_REQUESTS_PER_MINUTE` and `MODEL_REQUESTS_PER_DAY`, if different limits are required

The service uses `/health` as its health check. The Docker image starts Uvicorn on the platform-provided `PORT`, defaulting to `7860`.

### Frontend on Vercel

Build the Angular application from `frontend/`. Update `frontend/src/environments/environment.ts` when the backend deployment URL changes. The frontend production build is configured through `frontend/vercel.json` and `angular.json`.

### Backend on Vercel

If the frontend points to the Vercel API, configure these project environment variables in Vercel before deploying the backend:

- `MONGODB_URL`
- `MONGODB_DB_NAME`
- `AUTH_SECRET` — one long random value that remains unchanged between deployments
- `GROQ_API_KEYS` and `GEMINI_API_KEYS`

The backend `vercel.json` sets `APP_ENV=production` and allows the deployed frontend origins. After changing `AUTH_SECRET`, sign in again so the browser receives a cookie signed with the current secret.

## Project Layout

```text
paper-checker/
├── backend/
│   ├── app/
│   │   ├── core/              # Logging, security, request budgeting
│   │   ├── grading/           # Extraction, providers, and graders
│   │   ├── models/            # Pydantic API and persistence models
│   │   ├── repositories/      # MongoDB access
│   │   ├── routers/           # FastAPI endpoints
│   │   └── main.py            # FastAPI application
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/app/core/          # Shared services and models
│   ├── src/app/features/      # Answer keys, submissions, batches, reports
│   └── src/environments/      # API endpoint configuration
├── render.yaml
└── README.md
```

## Security Notes

- Keep provider keys, MongoDB credentials, and `API_KEY` in environment variables.
- Use HTTPS for deployed frontend and backend services.
- Set an exact production frontend origin in `CORS_ORIGINS`.
- The default request budget is process-local; use a shared Redis-backed limiter when deploying multiple backend workers.
- Uploaded papers can contain student personal information. Restrict database and storage access appropriately.
