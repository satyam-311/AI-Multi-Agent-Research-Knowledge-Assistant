# schemas.py
# Pydantic request and response models for the MARKA API.
# These schemas define the serialization contract between the FastAPI routes
# and their callers (frontend, external clients). They also drive OpenAPI
# documentation generation and request validation.

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field


class HealthResponse(BaseModel):
    """
    Response body for the GET /health liveness check endpoint.

    Attributes:
        status (str): Always "ok" when the server is running.
        message (str): Human-readable confirmation string.
    """

    status: str
    message: str


class DocumentUploadResponse(BaseModel):
    """
    Response body returned after a successful PDF document upload and indexing.

    Attributes:
        document_id (int): PostgreSQL primary key of the newly created document record.
        user_id (int): Owner of the uploaded document.
        filename (str): Original filename of the uploaded PDF.
        chunks_created (int): Number of text chunks indexed into ChromaDB.
    """

    document_id: int = Field(examples=[13])
    user_id: int = Field(examples=[1])
    filename: str = Field(examples=["research-paper.pdf"])
    chunks_created: int = Field(examples=[8])


class AskRequest(BaseModel):
    """
    Request body for the POST /chat and POST /rag/ask_question endpoints.

    Attributes:
        user_id (int | None): The user's ID. If None, resolved from the JWT token.
        question (str): The raw question text submitted by the user.
        top_k (int): Number of ChromaDB chunks to retrieve. Clamped to [1, 20].
        document_id (int | None): If provided, restricts retrieval to this document.
            If None, the query searches across all the user's documents or routes
            to ArXiv/web search if the query matches research keywords.
    """

    user_id: int | None = Field(default=None, ge=1, examples=[1])
    question: str = Field(examples=["What is the use of logistic regression?"])
    top_k: int = Field(default=4, ge=1, le=20, examples=[4])
    document_id: int | None = Field(default=None, ge=1, examples=[13])


class SourceItem(BaseModel):
    """
    A single cited source in an answer response.

    Sources can come from three agent paths:
    - "rag": A chunk from the user's uploaded PDF documents.
    - "arxiv": An academic paper from the ArXiv API.
    - "ddg": A web result from the Tavily search API.

    Attributes:
        type (Literal): The source type string, one of "rag", "arxiv", or "ddg".
        title (str | None): Display title for the source.
        pdf_url (str | None): Direct PDF download URL (ArXiv sources).
        summary (str | None): Short excerpt or abstract snippet.
        link (str | None): URL of the source page or PDF.
        published_at (str | None): ISO 8601 publication date (ArXiv sources).
    """

    type: Literal["rag", "arxiv", "ddg"] = Field(examples=["arxiv"])
    title: str | None = Field(default=None, examples=["Attention Is All You Need"])
    pdf_url: str | None = Field(default=None, examples=["https://arxiv.org/pdf/1706.03762.pdf"])
    summary: str | None = Field(default=None, examples=["Transformer architecture summary."])
    link: str | None = Field(default=None, examples=["https://arxiv.org/pdf/1706.03762.pdf"])
    published_at: str | None = Field(default=None, examples=["2017-06-12"])


class SourceGroups(BaseModel):
    """
    Grouped source citations organized by agent type.

    The three-key structure allows the frontend to render source sections
    separately (document sources, academic papers, web results) rather than
    mixing them in a single flat list.

    Attributes:
        rag (list[SourceItem]): Sources from ChromaDB document retrieval.
        arxiv (list[SourceItem]): Sources from ArXiv academic paper search.
        ddg (list[SourceItem]): Sources from Tavily web search.
    """

    rag: list[SourceItem] = Field(default_factory=list)
    arxiv: list[SourceItem] = Field(default_factory=list)
    ddg: list[SourceItem] = Field(default_factory=list)


class AskResponse(BaseModel):
    """
    Response body for the POST /chat and POST /rag/ask_question endpoints.

    Attributes:
        user_id (int): The ID of the user who asked the question.
        answer (str): The LLM-generated or formatted answer string.
        sources (SourceGroups): Cited sources grouped by agent type.
    """

    user_id: int = Field(examples=[1])
    answer: str = Field(
        examples=["Logistic regression is commonly used for binary classification problems."]
    )
    sources: SourceGroups = Field(
        examples=[
            {
                "rag": [],
                "arxiv": [
                    {
                        "type": "arxiv",
                        "title": "Attention Is All You Need",
                        "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
                        "summary": "Transformer architecture summary.",
                        "link": "https://arxiv.org/pdf/1706.03762.pdf",
                        "published_at": "2017-06-12",
                    }
                ],
                "ddg": [],
            }
        ]
    )


class DocumentOut(BaseModel):
    """
    Serialized document record returned in the GET /rag/documents response.

    Attributes:
        id (int): PostgreSQL primary key.
        user_id (int): Owner of the document.
        filename (str): Original PDF filename.
        content_preview (str): First 500 characters of extracted text.
        created_at (datetime): UTC timestamp of document upload.
    """

    id: int
    user_id: int
    filename: str
    content_preview: str
    created_at: datetime

    class Config:
        # from_attributes=True enables direct construction from SQLAlchemy ORM instances
        from_attributes = True


class ChatHistoryOut(BaseModel):
    """
    Serialized chat history record returned in the GET /chat/history response.

    Attributes:
        id (int): PostgreSQL primary key.
        user_id (int): The user who asked the question.
        document_id (int | None): The document the question was scoped to, or None
            for research queries that used the ArXiv/web path.
        question (str): The original question text.
        answer (str): The generated answer.
        sources (list[SourceItem]): Cited sources deserialized from sources_json.
        created_at (datetime): UTC timestamp of the interaction.
    """

    id: int
    user_id: int
    document_id: int | None
    question: str
    answer: str
    sources: list[SourceItem]
    created_at: datetime


class DeleteDocumentResponse(BaseModel):
    """
    Response body for the DELETE /rag/documents/{document_id} endpoint.

    Attributes:
        document_id (int): The ID of the document that was deleted.
        deleted (bool): Always True on a successful deletion.
    """

    document_id: int = Field(examples=[13])
    deleted: bool = Field(examples=[True])


class RegisterRequest(BaseModel):
    """
    Request body for the POST /auth/register endpoint.

    Attributes:
        name (str): User display name (2-120 characters).
        email (str): Email address (5-255 characters); stored lowercase-normalized.
        password (str): Plaintext password (8-128 characters); hashed before storage.
    """

    name: str = Field(min_length=2, max_length=120, examples=["Jane Doe"])
    email: str = Field(min_length=5, max_length=255, examples=["satyam@example.com"])
    password: str = Field(min_length=8, max_length=128, examples=["strongpassword123"])


class LoginRequest(BaseModel):
    """
    Request body for the POST /auth/login endpoint.

    Attributes:
        email (str): Email address of the existing account.
        password (str): Plaintext password to verify against the stored hash.
    """

    email: str = Field(min_length=5, max_length=255, examples=["satyam@example.com"])
    password: str = Field(min_length=8, max_length=128, examples=["strongpassword123"])


class GoogleLoginRequest(BaseModel):
    """
    Request body for the POST /auth/google Google OAuth endpoint.

    The id_token field accepts both "idToken" (camelCase, as sent by the Firebase
    Web SDK) and "id_token" (snake_case) via AliasChoices for broader compatibility.

    Attributes:
        id_token (str): Firebase Google ID token from signInWithPopup().
            Minimum 20 characters to reject obviously invalid values early.
    """

    id_token: str = Field(
        min_length=20,
        # Accept both camelCase (frontend) and snake_case (API test clients)
        validation_alias=AliasChoices("idToken", "id_token"),
        serialization_alias="idToken",
    )


class UserOut(BaseModel):
    """
    Serialized user profile returned in auth responses and GET /auth/me.

    Attributes:
        id (int): PostgreSQL primary key.
        name (str): User display name.
        email (str): Normalized email address.
        created_at (datetime): UTC timestamp of account creation.
    """

    id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        # from_attributes=True enables direct construction from SQLAlchemy ORM instances
        from_attributes = True


class AuthResponse(BaseModel):
    """
    Response body returned by all successful authentication endpoints
    (register, login, google).

    Attributes:
        token (str): The signed HMAC-SHA256 JWT for subsequent authenticated requests.
        user (UserOut): The authenticated user's profile data.
    """

    token: str
    user: UserOut
