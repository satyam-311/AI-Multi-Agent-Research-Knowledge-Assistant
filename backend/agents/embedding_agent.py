from config import get_settings
from services.embedding_backend import load_embedding_model
from services.vector_store import delete_document_chunks, upsert_document_chunks


class EmbeddingModelUnavailable(RuntimeError):
    pass


class EmbeddingAgent:
    def __init__(self) -> None:
        settings = get_settings()
        try:
            self.model = load_embedding_model()
        except Exception as exc:  # network/proxy/offline/corrupt cache, etc.
            raise EmbeddingModelUnavailable(
                "Embedding model could not be loaded. "
                "Check the local embedding setup and pgvector/Postgres configuration, then restart the server. "
                f"(EMBEDDING_MODEL={settings.embedding_model}). "
                f"Root error: {exc.__class__.__name__}: {exc}"
            ) from exc

    def index_document_chunks(
        self, user_id: int, document_id: int, filename: str, chunks: list[str]
    ) -> None:
        if not chunks:
            return

        # Re-indexing the same document should replace previous chunks cleanly.
        self.delete_document_chunks(user_id=user_id, document_id=document_id)

        embeddings = self.model.encode(chunks)
        if hasattr(embeddings, "tolist"):
            embeddings = embeddings.tolist()
        upsert_document_chunks(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            chunks=chunks,
            embeddings=embeddings,
        )

    def delete_document_chunks(self, user_id: int, document_id: int) -> None:
        delete_document_chunks(user_id=user_id, document_id=document_id)
