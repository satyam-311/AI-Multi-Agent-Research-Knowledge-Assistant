# models.py
# SQLAlchemy ORM models defining the MARKA PostgreSQL schema.
# Three tables support the application: users (auth identity), documents
# (uploaded PDFs), and chat_history (per-user Q&A records with cited sources).

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Shared declarative base that registers these models for create_all() and migration
from backend.database import Base


class User(Base):
    """
    Represents an authenticated MARKA user.

    Stores both email/password credential users (with a bcrypt-style PBKDF2 hash
    in password_hash) and Google OAuth users (with an empty password_hash). The
    email field is always stored lowercase-normalized to prevent duplicate accounts
    from case-variant submissions.

    Attributes:
        id (int): Auto-increment primary key; used as the ChromaDB namespace key.
        name (str): Display name shown in the UI (2-120 characters).
        email (str): Unique, normalized email address used for login lookup.
        password_hash (str): PBKDF2-SHA256 hash in "{salt}${digest}" format,
            or an empty string for OAuth-only accounts.
        created_at (datetime): UTC timestamp of account creation (server default).
        documents (list[Document]): All documents uploaded by this user.
        chats (list[ChatHistory]): All Q&A records generated for this user.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Unique index on email enables O(1) lookup during login and registration checks
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    documents: Mapped[list["Document"]] = relationship(back_populates="user")
    chats: Mapped[list["ChatHistory"]] = relationship(back_populates="user")


class Document(Base):
    """
    Represents a PDF document uploaded by a user.

    Stores both a short preview (first 500 characters) for display in the documents
    list and the full extracted text as a RAG fallback when ChromaDB is unavailable.
    The document record is created before ChromaDB indexing so a valid document.id
    exists to use as the vector namespace key.

    Attributes:
        id (int): Auto-increment primary key; used as the ChromaDB document_id metadata field.
        user_id (int): FK to users.id; scopes document access to the owning user.
        filename (str): Original PDF filename as uploaded; used as the source citation title.
        content_preview (str): First 500 characters of extracted text for list display.
        content_text (str): Full extracted text, used as the PostgreSQL RAG fallback.
        created_at (datetime): UTC timestamp of upload (server default).
        user (User): The owning user relationship.
        chats (list[ChatHistory]): Q&A records scoped to this document.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Index on user_id enables fast listing of all documents for a given user
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_preview: Mapped[str] = mapped_column(Text, default="")
    content_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="documents")
    chats: Mapped[list["ChatHistory"]] = relationship(back_populates="document")


class ChatHistory(Base):
    """
    Represents a single Q&A interaction in the MARKA chat system.

    Stores the user's question, the generated answer, and the serialized sources
    JSON that was cited in the response. The document_id is nullable to support
    research queries that are not scoped to any uploaded document (ArXiv/web path).

    Attributes:
        id (int): Auto-increment primary key.
        user_id (int): FK to users.id; identifies the user who asked the question.
        document_id (int | None): FK to documents.id; None for research-path queries
            that are not associated with an uploaded document.
        question (str): The original user question text.
        answer (str): The full LLM-generated answer including any formatted sources.
        sources_json (str): JSON array of SourceItem dicts serialized as a TEXT column,
            denormalized for fast retrieval without a join to a separate sources table.
        created_at (datetime): UTC timestamp of the Q&A interaction (server default).
        user (User): The user who generated this chat record.
        document (Document): The document this chat was scoped to, or None.
    """

    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Indexes on user_id and document_id support the common query pattern:
    # "fetch all chats for user X scoped to document Y"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # sources_json stores the full source payload as serialized JSON to avoid
    # a separate sources table and the join overhead on every history fetch
    sources_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="chats")
    document: Mapped["Document"] = relationship(back_populates="chats")
