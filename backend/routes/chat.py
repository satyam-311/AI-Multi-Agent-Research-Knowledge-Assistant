# routes/chat.py
# FastAPI route handlers for the MARKA chat interface.
# Provides the primary question-answering endpoint and per-document chat history
# retrieval. Both endpoints support optional authentication: authenticated users
# are identified by their JWT token; unauthenticated requests fall back to a
# user_id query parameter.

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.database import get_db
from backend.services.auth_service import AuthService, get_auth_cookie, get_bearer_token
from backend.services.rag_service import RAGService
# normalize_source_items converts raw sources_json into validated SourceItem dicts
from backend.services.source_utils import normalize_source_items

router = APIRouter()
# Single service instances per worker process to reuse the orchestrator and its agents
rag_service = RAGService()
auth_service = AuthService()


def get_optional_authenticated_user(
    authorization: str | None = Depends(get_bearer_token),
    access_token: str | None = Depends(get_auth_cookie),
    db: Session = Depends(get_db),
) -> models.User | None:
    """
    FastAPI dependency that returns the current user if authenticated, or None.

    Unlike a required auth dependency (which raises 401), this allows the chat
    and history endpoints to serve both authenticated and unauthenticated requests.
    Unauthenticated requests fall back to using the user_id from the request body.

    Args:
        authorization (str | None): Authorization header value from get_bearer_token.
        access_token (str | None): Cookie value from get_auth_cookie.
        db (Session): Per-request SQLAlchemy session from get_db.

    Returns:
        models.User | None: The authenticated user, or None if no valid token is present.
    """
    try:
        return auth_service.get_current_user(
            db=db, authorization=authorization, access_token=access_token
        )
    except Exception:
        # Suppress all auth errors so the endpoint degrades gracefully for
        # unauthenticated clients rather than returning a 401
        return None


def resolve_user_id(current_user: models.User | None, requested_user_id: int | None = None) -> int:
    """
    Determine the effective user_id for a request.

    Priority order:
    1. JWT-authenticated user (most trusted; cannot be spoofed by the client).
    2. Explicit user_id from the request body (trusted only when no JWT is present).
    3. Fallback to user_id=1 for unauthenticated requests without a user_id field.

    Args:
        current_user (models.User | None): The authenticated user, or None.
        requested_user_id (int | None): The user_id from the request body, or None.

    Returns:
        int: The resolved user_id to use for all downstream operations.
    """
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
    """
    Submit a question to the multi-agent RAG pipeline and receive a grounded answer.

    Routes the question through the orchestrator's adaptive routing logic:
    - Research queries (containing "arxiv", "research paper", etc.) -> ArXiv agent.
    - All other queries -> ChromaDB vector search with optional web search fallback.

    Args:
        payload (schemas.AskRequest): Contains question text, optional document_id,
            top_k chunk count, and optional user_id.
        current_user (models.User | None): Injected by get_optional_authenticated_user.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        schemas.AskResponse: The generated answer and grouped source citations.
    """
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
    """
    Retrieve the chat history for a specific document, ordered newest-first.

    Fetches ChatHistory rows from PostgreSQL filtered by user_id and document_id.
    The sources_json TEXT column is deserialized back into SourceItem objects
    for each row so the response conforms to the ChatHistoryOut schema.

    Args:
        document_id (int): Required; restricts history to this document. Must be >= 1.
        user_id (int | None): Optional fallback user_id when no JWT is present.
        limit (int): Maximum number of history rows to return. Clamped to [1, 500].
        current_user (models.User | None): Injected by get_optional_authenticated_user.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        list[schemas.ChatHistoryOut]: Chat records ordered by created_at descending,
        each with deserialized source citations.
    """
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
            # Deserialize the sources_json TEXT column back into a Python list
            sources = json.loads(row.sources_json)
        except json.JSONDecodeError:
            # Treat malformed JSON as an empty sources list rather than failing the request
            sources = []

        response.append(
            schemas.ChatHistoryOut(
                id=row.id,
                user_id=row.user_id,
                document_id=row.document_id,
                question=row.question,
                answer=row.answer,
                # normalize_source_items re-validates and deduplicates sources on read
                sources=normalize_source_items(sources),
                created_at=row.created_at,
            )
        )

    return response
