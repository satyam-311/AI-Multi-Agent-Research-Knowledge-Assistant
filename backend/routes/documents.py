from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from backend import schemas
from backend.auth.firebase_auth import get_user_id
from backend.database import get_db
from backend.services.rag_service import RAGService

router = APIRouter()
rag_service = RAGService()


@router.post("/upload", response_model=schemas.DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> schemas.DocumentUploadResponse:
    active_user_id = get_user_id(request)
    db_document, chunk_count = await rag_service.upload_document(db, active_user_id, file)
    return schemas.DocumentUploadResponse(
        document_id=db_document.id,
        user_id=active_user_id,
        filename=db_document.filename,
        chunks_created=chunk_count,
    )
