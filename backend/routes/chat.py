import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.database import get_db
from backend.services.auth_service import AuthService, get_auth_cookie, get_bearer_token
from backend.services.rag_service import RAGService
from backend.services.source_utils import normalize_source_items

router = APIRouter()
rag_service = RAGService()
auth_service = AuthService()

def get_optional_authenticated_user(
    authorization: str | None = Depends(get_bearer_token),
    access_token: str | None = Depends(get_auth_cookie),
    db: Session = Depends(get_db),
) -> models.User | None:
    try:
        return auth_service.get_current_user(
            db=db, authorization=authorization, access_token=access_token
        )
    except Exception:
        return None


def resolve_user_id(current_user: models.User | None, requested_user_id: int | None = None) -> int:
    if current_user is not None:
        return current_user.id
    if requested_user_id is not None and requested_user_id >= 1:
        return requested_user_id
    return 1


@router.post("", response_model=schemas.AskResponse)
def ask_question(
    payload: schemas.AskRequest,
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> schemas.AskResponse:
    active_user_id = resolve_user_id(current_user, payload.user_id)
    answer, sources = rag_service.ask_question(
        db=db,
        user_id=active_user_id,
        question=payload.question,
        top_k=payload.top_k,
        document_id=payload.document_id,
    )
    return schemas.AskResponse(user_id=active_user_id, answer=answer, sources=sources)


@router.get("/history", response_model=list[schemas.ChatHistoryOut])
def get_chat_history(
    document_id: int = Query(..., ge=1),
    user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> list[schemas.ChatHistoryOut]:
    active_user_id = resolve_user_id(current_user, user_id)
    rows = (
        db.query(models.ChatHistory)
        .filter(
            models.ChatHistory.user_id == active_user_id,
            models.ChatHistory.document_id == document_id,
        )
        .order_by(models.ChatHistory.created_at.desc())
        .limit(limit)
        .all()
    )

    response: list[schemas.ChatHistoryOut] = []
    for row in rows:
        try:
            sources = json.loads(row.sources_json)
        except json.JSONDecodeError:
            sources = []

        response.append(
            schemas.ChatHistoryOut(
                id=row.id,
                user_id=row.user_id,
                document_id=row.document_id,
                question=row.question,
                answer=row.answer,
                sources=normalize_source_items(sources),
                created_at=row.created_at,
            )
        )

    return response
