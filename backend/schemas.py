from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    message: str


class DocumentUploadResponse(BaseModel):
    document_id: int = Field(examples=[13])
    user_id: int = Field(examples=[1])
    filename: str = Field(examples=["research-paper.pdf"])
    chunks_created: int = Field(examples=[8])


class AskRequest(BaseModel):
    user_id: int | None = Field(default=None, ge=1, examples=[1])
    question: str = Field(examples=["What is the use of logistic regression?"])
    top_k: int = Field(default=4, ge=1, le=20, examples=[4])
    document_id: int | None = Field(default=None, ge=1, examples=[13])


class AskResponse(BaseModel):
    user_id: int = Field(examples=[1])
    answer: str = Field(
        examples=["Logistic regression is commonly used for binary classification problems."]
    )
    sources: list[str] = Field(examples=[["research-paper.pdf"]])


class DocumentOut(BaseModel):
    id: int
    user_id: int
    filename: str
    content_preview: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryOut(BaseModel):
    id: int
    user_id: int
    document_id: int | None
    question: str
    answer: str
    sources: list[str]
    created_at: datetime


class DeleteDocumentResponse(BaseModel):
    document_id: int = Field(examples=[13])
    deleted: bool = Field(examples=[True])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120, examples=["Jane Doe"])
    email: str = Field(min_length=5, max_length=255, examples=["satyam@example.com"])
    password: str = Field(min_length=8, max_length=128, examples=["strongpassword123"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255, examples=["satyam@example.com"])
    password: str = Field(min_length=8, max_length=128, examples=["strongpassword123"])


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(
        min_length=20,
        validation_alias=AliasChoices("idToken", "id_token"),
        serialization_alias="idToken",
    )


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    token: str
    user: UserOut
