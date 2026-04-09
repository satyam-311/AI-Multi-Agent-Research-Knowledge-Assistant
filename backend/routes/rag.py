import json

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.database import SessionLocal, get_db
from backend.services.auth_service import AuthService, get_auth_cookie, get_bearer_token
from backend.services.rag_service import RAGService

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


@router.post("/upload_document", response_model=schemas.DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    user_id: int | None = Form(default=None, ge=1, example=1),
    file: UploadFile = File(...),
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> schemas.DocumentUploadResponse:
    active_user_id = resolve_user_id(current_user, user_id)
    file_bytes = await file.read()
    filename = file.filename or "uploaded.pdf"
    content_type = file.content_type
    document = rag_service.create_processing_document(db, active_user_id, filename)
    background_tasks.add_task(
        process_uploaded_document_in_background,
        active_user_id,
        document.id,
        filename,
        content_type,
        file_bytes,
    )
    return schemas.DocumentUploadResponse(
        document_id=document.id,
        user_id=active_user_id,
        filename=document.filename,
        chunks_created=0,
        processing=True,
    )


async def process_uploaded_document_in_background(
    user_id: int,
    document_id: int,
    filename: str,
    content_type: str | None,
    file_bytes: bytes,
) -> None:
    db = SessionLocal()
    try:
        await rag_service.process_uploaded_document_bytes(
            db=db,
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
        )
    except Exception as exc:
        document = (
            db.query(models.Document)
            .filter(models.Document.id == document_id, models.Document.user_id == user_id)
            .first()
        )
        if document is not None:
            document.content_preview = f"Processing failed: {exc}"
            document.content_text = ""
            db.add(document)
            db.commit()
    finally:
        db.close()


@router.post("/ask_question", response_model=schemas.AskResponse)
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


@router.get("/documents", response_model=list[schemas.DocumentOut])
def list_documents(
    user_id: int | None = Query(default=None, ge=1),
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> list[schemas.DocumentOut]:
    query = db.query(models.Document).order_by(models.Document.created_at.desc())
    active_user_id = resolve_user_id(current_user, user_id)
    query = query.filter(models.Document.user_id == active_user_id)
    return query.all()


@router.get("/get_chat_history", response_model=list[schemas.ChatHistoryOut])
def get_chat_history(
    user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: models.User | None = Depends(get_optional_authenticated_user),
    db: Session = Depends(get_db),
) -> list[schemas.ChatHistoryOut]:
    query = db.query(models.ChatHistory).order_by(models.ChatHistory.created_at.desc())
    active_user_id = resolve_user_id(current_user, user_id)
    query = query.filter(models.ChatHistory.user_id == active_user_id)

    rows = query.limit(limit).all()
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
                sources=sources if isinstance(sources, list) else [],
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
    active_user_id = resolve_user_id(current_user, user_id)
    rag_service.delete_document(db=db, user_id=active_user_id, document_id=document_id)
    return schemas.DeleteDocumentResponse(document_id=document_id, deleted=True)
