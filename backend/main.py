# main.py
# FastAPI application entry point for the MARKA backend.
# Creates the FastAPI app instance, configures CORS middleware, runs database
# initialization on startup via the lifespan context, and mounts all API routers
# under both "/" and "/api/" prefixes for frontend compatibility.

import logging
# asynccontextmanager enables structured startup/shutdown logic without a separate event handler
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importing models here ensures all ORM classes are registered on the Base metadata
# before initialize_database() calls Base.metadata.create_all()
from backend import models  # noqa: F401
from backend.config import get_settings
from backend.database import initialize_database
# api_router aggregates all sub-routers (auth, chat, rag, health)
from backend.routes import api_router

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    FastAPI lifespan context manager that runs once at startup and shutdown.

    Calls initialize_database() to create missing tables and apply schema
    migrations before the first request is served. Database initialization
    failures are logged as warnings rather than crashing the server, so the
    application can still start in read-only or degraded mode.

    Args:
        _ (FastAPI): The FastAPI application instance (unused; required by the protocol).

    Yields:
        None: Control returns to FastAPI, which then begins serving requests.
    """
    try:
        initialize_database()
    except Exception as exc:
        # Non-fatal: log and continue so the server starts even if migrations fail
        logger.warning("Database initialization skipped during startup: %s", exc)
    yield


app = FastAPI(
    title="AI Multi-Agent Research Knowledge Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

# Build the set of CORS-allowed origins by merging configured origins with
# a fixed set of localhost addresses used during local development
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

# allow_credentials=True is required because the frontend sends the HttpOnly
# access_token cookie with each request; CORS blocks credentialed requests
# unless the origin is explicitly listed (wildcard "*" cannot be used here)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(configured_origins | local_dev_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers under both "/" and "/api/" so the frontend can use either prefix.
# The Next.js API client defaults to "/api/" while Swagger UI uses "/" directly.
app.include_router(api_router)
app.include_router(api_router, prefix="/api")
