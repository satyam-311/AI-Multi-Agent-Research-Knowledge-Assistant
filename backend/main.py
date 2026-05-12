import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import models  # noqa: F401
from backend.config import get_settings
from backend.database import initialize_database
from backend.routes import api_router

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        initialize_database()
    except Exception as exc:
        logger.warning("Database initialization skipped during startup: %s", exc)
    yield

app = FastAPI(
    title="AI Multi-Agent Research Knowledge Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

configured_origins = {
    origin.strip()
    for origin in settings.allowed_origins.split(",")
    if origin.strip()
}
local_dev_origins = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(configured_origins | local_dev_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(api_router, prefix="/api")
