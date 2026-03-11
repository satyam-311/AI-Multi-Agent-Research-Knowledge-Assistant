from fastapi import APIRouter

from backend.routes import auth, health, rag

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
