# routes/rag.py
# FastAPI route handlers for MARKA document management and RAG query operations.
# Provides PDF upload with embedding indexing, document listing, chat history
# retrieval, question answering, and document deletion with vector cleanup.

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.database import get_db
from backend.services.auth_service import AuthService, get_auth_cookie, get_bearer_token
from backend.services.rag_service import RAGService
from backend.services.source_utils import normalize_source_items

router = APIRouter()
# Single service instances per worker process to reuse the orchestrator's loaded models
rag_service = RAGService()
auth_service = AuthService()


def get_optional_authenticated_user(
    authorization: str | None = Depends(get_bearer_token),
    access_token: str | None = Depends(get_auth_cookie),
    db: Session = Depends(get_db),
) -> models.User | None:
    """
    FastAPI dependency that returns the current user if authenticated, or None.

    Allows all RAG endpoints to serve both authenticated (JWT-bearing) clients
    and unauthenticated clients that supply a user_id directly in the request.

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
        return None


def resolve_user_id(current_user: models.User | None, requested_user_id: int | None = None) -> int:
    """
    Determine the effective user_id for a request.

    Prioritizes the JWT-authenticated user's ID over any client-supplied user_id
    to prevent privilege escalation by unauthenticated clients.

    Args:
        current_user (models.User | None): The authenticated user, or None.
        requested_user_id (int | None): The user_id from the form or query parameter.

    Returns:
        int: The resolved user_id for all downstream database and ChromaDB operations.
    """
    if current_user is not None:
        return current_user.id
    if requested_user_id is not None and requested_user_id >= 1:
        return requested_user_id
    return 1


@router.post("/upload_document", response_model=schemas.DocumentUploadResponse)
async def upload_document(
    user_id: int | None = Form(default=None, ge=1, example=1),
    file: UploadFile = File(...),
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> schemas.DocumentUploadResponse:
    """
    Upload a PDF document and index it into the user's ChromaDB knowledge base.

    Runs the full four-stage ingestion pipeline: text extraction, chunking,
    sentence-transformer embedding, and ChromaDB vector indexing. The PostgreSQL
    document record is created mid-pipeline so a valid document_id exists for the
    ChromaDB namespace before vectors are written.

    Args:
        user_id (int | None): Fallback user_id from the multipart form when no JWT
            is present. Ignored if the request carries a valid auth token.
        file (UploadFile): The PDF file from the multipart request body.
        current_user (models.User | None): JWT-authenticated user, or None.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        schemas.DocumentUploadResponse: Document ID, owner ID, filename, and chunk count.

    Raises:
        HTTPException 400: PDF cannot be parsed, is empty, or has no extractable text.
        HTTPException 503: Embedding model is unavailable.
        HTTPException 500: ChromaDB indexing fails for any other reason.
    """
    active_user_id = resolve_user_id(current_user, user_id)
    document, chunk_count = await rag_service.upload_document(db, active_user_id, file)
    return schemas.DocumentUploadResponse(
        document_id=document.id,
        user_id=active_user_id,
        filename=document.filename,
        chunks_created=chunk_count,
    )


@router.post("/ask_question", response_model=schemas.AskResponse)
def ask_question(
    payload: schemas.AskRequest,
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> schemas.AskResponse:
    """
    Submit a question to the multi-agent pipeline and receive a grounded answer.

    Duplicate of the /chat endpoint; kept here for frontend clients that route
    question-answering through the /rag prefix alongside document management.

    Args:
        payload (schemas.AskRequest): Contains question, optional document_id, top_k, and user_id.
        current_user (models.User | None): JWT-authenticated user, or None.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        schemas.AskResponse: Generated answer and grouped source citations.
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


@router.get("/documents", response_model=list[schemas.DocumentOut])
def list_documents(
    user_id: int | None = Query(default=None, ge=1),
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> list[schemas.DocumentOut]:
    """
    List all documents belonging to the authenticated user, newest first.

    Args:
        user_id (int | None): Fallback user_id when no JWT is present.
        current_user (models.User | None): JWT-authenticated user, or None.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        list[schemas.DocumentOut]: All documents for the resolved user_id,
        ordered by created_at descending.
    """
    query = db.query(models.Document).order_by(models.Document.created_at.desc())
    active_user_id = resolve_user_id(current_user, user_id)
    query = query.filter(models.Document.user_id == active_user_id)
    return query.all()


@router.get("/get_chat_history", response_model=list[schemas.ChatHistoryOut])
def get_chat_history(
    user_id: int | None = Query(default=None, ge=1),
    document_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> list[schemas.ChatHistoryOut]:
    """
    Retrieve chat history for the authenticated user, optionally filtered by document.

    Deserializes the sources_json TEXT column for each row back into SourceItem
    objects. Malformed JSON rows are treated as having empty sources to avoid
    failing the whole request because of a single corrupted history entry.

    Args:
        user_id (int | None): Fallback user_id when no JWT is present.
        document_id (int | None): If provided, restricts history to this document only.
        limit (int): Maximum rows to return. Clamped to [1, 500]. Defaults to 50.
        current_user (models.User | None): JWT-authenticated user, or None.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        list[schemas.ChatHistoryOut]: Chat records ordered by created_at descending.
    """
    query = db.query(models.ChatHistory).order_by(models.ChatHistory.created_at.desc())
    active_user_id = resolve_user_id(current_user, user_id)
    query = query.filter(models.ChatHistory.user_id == active_user_id)
    if document_id is not None:
        query = query.filter(models.ChatHistory.document_id == document_id)

    rows = query.limit(limit).all()
    response: list[schemas.ChatHistoryOut] = []
    for row in rows:
        try:
            sources = json.loads(row.sources_json)
        except json.JSONDecodeError:
            # Treat a corrupted sources_json as empty rather than crashing the endpoint
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


@router.delete("/documents/{document_id}", response_model=schemas.DeleteDocumentResponse)
def delete_document(
    document_id: int,
    user_id: int | None = Query(default=None, ge=1),
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> schemas.DeleteDocumentResponse:
    """
    Delete a document and all its associated data.

    Orchestrates a two-store deletion: PostgreSQL (document row and linked chat
    history) followed by ChromaDB (all vector chunks for this document). The
    orchestrator verifies ownership before deleting to prevent one user from
    deleting another user's documents.

    Args:
        document_id (int): Path parameter; the PostgreSQL primary key of the document.
        user_id (int | None): Fallback user_id when no JWT is present.
        current_user (models.User | None): JWT-authenticated user, or None.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        schemas.DeleteDocumentResponse: The deleted document_id and deleted=True.

    Raises:
        HTTPException 404: If the document does not exist or does not belong to the user.
    """
    active_user_id = resolve_user_id(current_user, user_id)
    rag_service.delete_document(db=db, user_id=active_user_id, document_id=document_id)
    return schemas.DeleteDocumentResponse(document_id=document_id, deleted=True)
