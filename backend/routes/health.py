# routes/health.py
# FastAPI liveness check route for the MARKA backend.
# A single GET /health endpoint that returns a 200 OK response, used by load
# balancers, container orchestrators (Kubernetes, ECS), and monitoring tools
# to verify that the server process is running and accepting requests.

from fastapi import APIRouter

from backend.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """
    Return a static OK response confirming the API server is alive.

    This endpoint does not check database connectivity or agent availability;
    it is a pure liveness probe. Readiness checks (e.g. verifying ChromaDB
    and the LLM backend) are outside scope for this endpoint.

    Returns:
        HealthResponse: A response with status="ok" and a confirmation message.
    """
    return HealthResponse(status="ok", message="AI Multi-Agent backend is running")
