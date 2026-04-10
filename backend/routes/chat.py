from fastapi import APIRouter, Depends, Request

from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.firebase_auth import get_user_id
from backend.schemas import AskRequest, AskResponse
from backend.services.rag_service import RAGService

router = APIRouter()
rag_service = RAGService()


@router.post("/ask", response_model=AskResponse)
def ask_question(
    request: Request,
    payload: AskRequest,
    db: Session = Depends(get_db),
) -> AskResponse:
    active_user_id = get_user_id(request)
    answer, sources, flat_sources = rag_service.ask_question(
        db=db,
        user_id=active_user_id,
        question=payload.question,
        top_k=payload.top_k,
        document_id=payload.document_id,
    )
    return AskResponse(
        user_id=active_user_id,
        answer=answer,
        sources=sources,
        flat_sources=flat_sources,
    )
