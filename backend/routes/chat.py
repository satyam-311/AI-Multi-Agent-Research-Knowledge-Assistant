from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import AskRequest, AskResponse
from backend.services.rag_service import RAGService

router = APIRouter()
rag_service = RAGService()


@router.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    answer, sources = rag_service.ask_question(
        db=db,
        user_id=payload.user_id,
        question=payload.question,
        top_k=payload.top_k,
        document_id=payload.document_id,
    )
    return AskResponse(user_id=payload.user_id, answer=answer, sources=sources)
