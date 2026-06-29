# rag_service.py
# Thin service façade that connects FastAPI route handlers to the MultiAgentOrchestrator.
# Provides a stable interface for document upload, question answering, and document
# deletion so routes do not depend directly on the orchestrator's class structure.

# FastAPI UploadFile for the async document upload handler
from fastapi import UploadFile
# SQLAlchemy session passed through from the route's dependency injection
from sqlalchemy.orm import Session

# The orchestrator owns all agent coordination and routing logic
from backend.agents.orchestrator import MultiAgentOrchestrator


class RAGService:
    """
    Application service layer between FastAPI routes and the multi-agent orchestrator.

    Acts as a thin façade: all business logic lives in MultiAgentOrchestrator.
    This layer exists so route handlers call a stable, named method rather than
    instantiating or referencing the orchestrator directly, making the routes
    easier to test and the orchestrator easier to swap.

    Attributes:
        orchestrator (MultiAgentOrchestrator): The singleton orchestrator instance
            that coordinates all agents and manages the routing workflow.
    """

    def __init__(self) -> None:
        self.orchestrator = MultiAgentOrchestrator()

    async def upload_document(self, db: Session, user_id: int, file: UploadFile):
        """
        Delegate PDF ingestion to the orchestrator's upload pipeline.

        Args:
            db (Session): Active SQLAlchemy session for PostgreSQL writes.
            user_id (int): Owner of the uploaded document.
            file (UploadFile): Multipart PDF file from the FastAPI route.

        Returns:
            tuple[models.Document, int]: The saved Document ORM record and the
            number of ChromaDB chunks created.
        """
        return await self.orchestrator.upload_document(db, user_id, file)

    def ask_question(
        self,
        db: Session,
        user_id: int,
        question: str,
        top_k: int,
        document_id: int | None,
    ):
        """
        Delegate question routing and answer generation to the orchestrator.

        Args:
            db (Session): Active SQLAlchemy session for document reads and history writes.
            user_id (int): Authenticated user's ID, used to scope ChromaDB queries.
            question (str): Raw question text from the API request.
            top_k (int): Maximum number of vector chunks to retrieve from ChromaDB.
            document_id (int | None): If provided, restricts retrieval to one document.

        Returns:
            tuple[str, dict[str, list[dict]]]: The generated answer and grouped source dicts.
        """
        return self.orchestrator.ask_question(db, user_id, question, top_k, document_id)

    def delete_document(self, db: Session, user_id: int, document_id: int) -> None:
        """
        Delegate document deletion (PostgreSQL + ChromaDB) to the orchestrator.

        Args:
            db (Session): Active SQLAlchemy session for the delete operations.
            user_id (int): Must match the document owner to prevent unauthorized deletion.
            document_id (int): PostgreSQL primary key of the document to remove.

        Returns:
            None
        """
        self.orchestrator.delete_document(db, user_id, document_id)
