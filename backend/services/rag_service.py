from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.agents.orchestrator import MultiAgentOrchestrator


class RAGService:
    def __init__(self) -> None:
        self.orchestrator = MultiAgentOrchestrator()

    async def upload_document(self, db: Session, user_id: int, file: UploadFile):
        return await self.orchestrator.upload_document(db, user_id, file)

    def ask_question(self, db: Session, user_id: int, question: str, top_k: int, document_id: int | None):
        return self.orchestrator.ask_question(db, user_id, question, top_k, document_id)

    def delete_document(self, db: Session, user_id: int, document_id: int) -> None:
        self.orchestrator.delete_document(db, user_id, document_id)
