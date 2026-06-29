# routes/documents.py
# Legacy document upload route for the MARKA backend.
# Provides a simplified POST /upload endpoint used by early frontend versions
# and direct API clients. The primary upload path is POST /rag/upload_document
# in routes/rag.py, which includes authentication support and richer responses.

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
    """
    Upload a PDF document and index it into the user's ChromaDB knowledge base.

    This is the legacy upload endpoint; it requires an explicit user_id form field
    rather than inferring the user from a JWT token. New integrations should use
    POST /rag/upload_document, which supports optional Firebase authentication.

    Args:
        user_id (int): Required form field; the ID of the document owner.
        file (UploadFile): The PDF file from the multipart request body.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        schemas.DocumentUploadResponse: Document ID, owner ID, filename, and chunk count.

    Raises:
        HTTPException 400: PDF cannot be parsed, is empty, or has no extractable text.
        HTTPException 503: Embedding model is unavailable.
        HTTPException 500: ChromaDB indexing fails for any other reason.
    """
    db_document, chunk_count = await rag_service.upload_document(db, user_id, file)
    return schemas.DocumentUploadResponse(
        document_id=db_document.id,
        user_id=user_id,
        filename=db_document.filename,
        chunks_created=chunk_count,
    )
