# retrieval_agent.py
# ChromaDB vector similarity search interface for the MARKA RAG pipeline.
# Embeds the user's query using the same sentence-transformer model used
# during document ingestion, then queries ChromaDB for the top-k most
# similar chunks scoped to the authenticated user's namespace.

# Embedding model loader with LocalFallbackEmbedder for offline environments
from backend.services.embedding_backend import load_embedding_model
# ChromaDB collection accessor and metadata filter builder
from backend.services.vector_store import build_metadata_filter, get_document_collection


class RetrievalAgent:
    """
    Vector similarity search agent that queries the ChromaDB document collection.

    Embeds an incoming query using the same sentence-transformer model that was
    used during document ingestion (all-MiniLM-L6-v2, 384 dimensions), ensuring
    the query vector lives in the same embedding space as the stored chunk vectors.

    ChromaDB returns L2 distances; this agent converts them to cosine similarity
    scores in the [0, 1] range using the formula: similarity = 1 - distance.
    Scores above 0.5 are considered confident matches by the orchestrator.

    Attributes:
        model: The sentence-transformer model (or LocalFallbackEmbedder) used
            to embed queries. Loaded once at construction time.
        collection: The shared ChromaDB collection containing all indexed chunks
            across all users and documents.
    """

    def __init__(self) -> None:
        # Load the embedding model once at agent construction time to avoid
        # re-downloading or re-initializing on every query
        self.model = load_embedding_model()
        self.collection = get_document_collection()

    def retrieve_relevant_chunks(
        self, query: str, user_id: int, top_k: int = 4, document_id: int | None = None
    ) -> list[dict]:
        """
        Embed the query and retrieve the top-k most similar document chunks from ChromaDB.

        The ChromaDB metadata filter scopes the search to chunks belonging to the
        given user_id (and optionally a specific document_id) so one user cannot
        read another user's vectors. Results are returned ordered by ascending distance
        (most similar first).

        Args:
            query (str): The user's question text; embedded on the fly using the
                same model used during ingestion.
            user_id (int): Restricts ChromaDB results to this user's chunks only.
            top_k (int): Number of chunks to retrieve. Clamped to [1, 20] to prevent
                excessively large prompts. Defaults to 4.
            document_id (int | None): If provided, further restricts results to chunks
                from that specific document. None searches across all user documents.

        Returns:
            list[dict]: Each element contains the chunk text, distance, computed similarity
            score, and all metadata stored at index time (user_id, document_id, source,
            chunk_index).
        """
        # Embed the query as a list to match the batch input expected by sentence-transformers
        query_embeddings = self.model.encode([query])
        # Convert numpy array to plain Python list if the model returned a numpy type,
        # since ChromaDB expects native Python lists for query_embeddings
        if hasattr(query_embeddings, "tolist"):
            query_embeddings = query_embeddings.tolist()
        query_embedding = query_embeddings[0]

        results = self.collection.query(
            query_embeddings=[query_embedding],
            # Clamp top_k to [1, 20] to stay within ChromaDB's minimum result requirement
            # and to prevent oversized prompts that could exceed the LLM context window
            n_results=max(1, min(top_k, 20)),
            where=build_metadata_filter(user_id, document_id),
            include=["documents", "metadatas", "distances"],
        )

        # ChromaDB returns results as nested lists (one per query); extract the first (only) result
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        response = []
        for idx, text in enumerate(documents):
            metadata = metadatas[idx] if idx < len(metadatas) else {}
            distance = float(distances[idx]) if idx < len(distances) else 1.0
            # Convert L2 distance to a [0, 1] similarity score:
            # distance=0 means identical vectors (similarity=1.0),
            # distance=1 means orthogonal vectors (similarity=0.0)
            similarity = max(0.0, min(1.0, 1.0 - distance))
            response.append(
                {
                    "text": text,
                    "distance": distance,
                    "similarity": similarity,
                    # Spread all indexed metadata fields (source filename, chunk_index, etc.)
                    **metadata,
                }
            )
        return response
