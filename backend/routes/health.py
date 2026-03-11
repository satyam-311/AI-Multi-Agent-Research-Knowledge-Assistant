from fastapi import APIRouter

from backend.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", message="AI Multi-Agent backend is running")
