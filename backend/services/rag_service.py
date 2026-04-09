from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.agents.orchestrator import MultiAgentOrchestrator
from backend.services.multi_source_assistant_service import MultiSourceAssistantService


class RAGService:
    def __init__(self) -> None:
        self.orchestrator = MultiAgentOrchestrator()
        self.multi_source_assistant = MultiSourceAssistantService()

    async def upload_document(self, db: Session, user_id: int, file: UploadFile):
        return await self.orchestrator.upload_document(db, user_id, file)

    def create_processing_document(self, db: Session, user_id: int, filename: str):
        return self.orchestrator.create_processing_document(db, user_id, filename)

    async def process_uploaded_document_bytes(
        self,
        db: Session,
        user_id: int,
        document_id: int,
        filename: str,
        content_type: str | None,
        file_bytes: bytes,
    ):
        return await self.orchestrator.process_uploaded_document_bytes(
            db=db,
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
        )

    def ask_question(
        self,
        db: Session,
        user_id: int,
        question: str,
        top_k: int,
        document_id: int | None,
    ):
        return self.multi_source_assistant.ask_question(
            db=db,
            user_id=user_id,
            question=question,
            top_k=top_k,
            document_id=document_id,
        )

    def delete_document(self, db: Session, user_id: int, document_id: int) -> None:
        self.orchestrator.delete_document(db, user_id, document_id)
