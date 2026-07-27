from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import setup_logging
from app.db import close_mongo_connection, connect_to_mongo
from app.routers import answer_keys, grading, reports, submissions


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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(answer_keys.router)
app.include_router(submissions.router)
app.include_router(grading.router)
app.include_router(reports.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
