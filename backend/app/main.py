from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import setup_logging
from app.core.security import get_user_id_from_token, reset_current_user_id, set_current_user_id
from app.db import close_mongo_connection, connect_to_mongo
from app.routers import answer_keys, auth, batches, grading, reports, submissions


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(title="Markup API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_authenticated_user(request, call_next):
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else None
    context_token = set_current_user_id(get_user_id_from_token(token) if token else None)
    try:
        return await call_next(request)
    finally:
        reset_current_user_id(context_token)

app.include_router(answer_keys.router)
app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(submissions.router)
app.include_router(grading.router)
app.include_router(reports.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
