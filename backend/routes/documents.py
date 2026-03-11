from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from backend import schemas
from backend.database import get_db
from backend.services.rag_service import RAGService

router = APIRouter()
rag_service = RAGService()


@router.post("/upload", response_model=schemas.DocumentUploadResponse)
async def upload_document(
    user_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> schemas.DocumentUploadResponse:
    db_document, chunk_count = await rag_service.upload_document(db, user_id, file)
    return schemas.DocumentUploadResponse(
        document_id=db_document.id,
        user_id=user_id,
        filename=db_document.filename,
        chunks_created=chunk_count,
    )
