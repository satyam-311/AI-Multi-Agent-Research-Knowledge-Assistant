# routes/__init__.py
# Router registry for the MARKA backend API.
# Assembles all sub-routers (health, auth, chat, rag) into a single api_router
# that main.py mounts under both "/" and "/api/" prefixes.

from fastapi import APIRouter

from backend.routes import auth, chat, health, rag

# Master router that aggregates all feature-specific routers
api_router = APIRouter()

# Health check has no prefix so it resolves at /health and /api/health
api_router.include_router(health.router, tags=["health"])

# Prefix each feature router with its domain; the tag groups endpoints in Swagger UI
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
