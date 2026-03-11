from backend.config import get_settings
from backend.services.embedding_backend import load_embedding_model
from backend.services.vector_store import build_metadata_filter, get_document_collection


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
                "Check the local embedding setup and Chroma configuration, then restart the server. "
                f"(EMBEDDING_MODEL={settings.embedding_model}). "
                f"Root error: {exc.__class__.__name__}: {exc}"
            ) from exc
        self.collection = get_document_collection()

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
        ids = [f"{document_id}_{idx}" for idx in range(len(chunks))]
        metadatas = [
            {
                "user_id": user_id,
                "document_id": document_id,
                "source": filename,
                "chunk_index": idx,
            }
            for idx, _ in enumerate(chunks)
        ]

        self.collection.add(
            ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas
        )

    def delete_document_chunks(self, user_id: int, document_id: int) -> None:
        self.collection.delete(where=build_metadata_filter(user_id, document_id))
