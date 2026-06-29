# embedding_agent.py
# ChromaDB vector indexing agent for the MARKA document ingestion pipeline.
# Encodes text chunks produced by DocumentProcessingAgent into 384-dimensional
# dense vectors using the sentence-transformer model and persists them to the
# shared ChromaDB collection, namespaced by (user_id, document_id).

# Application settings (embedding model name for error messages)
from backend.config import get_settings
# Embedding model loader: returns SentenceTransformer or LocalFallbackEmbedder
from backend.services.embedding_backend import load_embedding_model
# ChromaDB collection accessor and metadata filter builder for scoped deletes
from backend.services.vector_store import build_metadata_filter, get_document_collection


class EmbeddingModelUnavailable(RuntimeError):
    """
    Raised when the sentence-transformer model cannot be loaded at agent construction.

    Caught by the orchestrator and re-raised as an HTTPException 503 so the
    frontend knows the embedding service is temporarily unavailable.
    """
    pass


class EmbeddingAgent:
    """
    Vector indexing agent that encodes text chunks and stores them in ChromaDB.

    Loaded once per MultiAgentOrchestrator instance (lazy singleton). At construction
    time it attempts to load the configured sentence-transformer model; if this fails
    (e.g. no internet access, corrupt model cache), it raises EmbeddingModelUnavailable
    so the server can report a clean 503 error rather than failing silently later.

    ChromaDB documents are stored with the following metadata per chunk:
        - user_id: scopes retrieval to the document owner
        - document_id: scopes retrieval to a specific document
        - source: original PDF filename for citation display
        - chunk_index: position of the chunk within the document

    Attributes:
        model: SentenceTransformer or LocalFallbackEmbedder for encoding text to vectors.
        collection: The shared ChromaDB collection that stores all users' chunks.
    """

    def __init__(self) -> None:
        settings = get_settings()
        try:
            self.model = load_embedding_model()
        except Exception as exc:
            # Wrap any model loading failure in a typed exception so the orchestrator
            # can return a structured 503 response rather than an unhandled 500
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
        """
        Encode text chunks into vectors and add them to the ChromaDB collection.

        Deletes any previously indexed chunks for this (user_id, document_id) pair
        before inserting new ones, so re-uploading the same document always produces
        a clean, consistent index without stale vectors from older versions.

        Args:
            user_id (int): Owner of the document; used as a ChromaDB metadata filter key
                to namespace vectors and prevent cross-user access.
            document_id (int): PostgreSQL primary key of the document; used alongside
                user_id to scope ChromaDB queries to a single document.
            filename (str): Original PDF filename stored as the "source" metadata field,
                which appears as the citation title in the API response.
            chunks (list[str]): Text chunks produced by DocumentProcessingAgent.chunk_text.

        Returns:
            None
        """
        if not chunks:
            return

        # Delete existing vectors for this document before re-indexing to avoid
        # accumulating stale chunks from earlier uploads of the same file
        self.delete_document_chunks(user_id=user_id, document_id=document_id)

        embeddings = self.model.encode(chunks)
        # Convert numpy array to plain Python list if the model returned a numpy type,
        # since ChromaDB's add method expects native Python lists
        if hasattr(embeddings, "tolist"):
            embeddings = embeddings.tolist()

        # Construct deterministic IDs so the same chunk always maps to the same ID,
        # enabling clean replacement when delete + re-add is performed
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
        """
        Remove all ChromaDB vectors associated with a specific (user_id, document_id) pair.

        Called both during re-indexing (before inserting new vectors) and during
        document deletion (after removing the PostgreSQL record). The metadata filter
        ensures only the target user's vectors for the target document are deleted.

        Args:
            user_id (int): Owner filter; prevents deletion of other users' vectors.
            document_id (int): Document filter; removes only chunks for this document.

        Returns:
            None
        """
        self.collection.delete(where=build_metadata_filter(user_id, document_id))
