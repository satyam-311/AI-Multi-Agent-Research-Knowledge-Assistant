from backend.services.embedding_backend import load_embedding_model
from backend.services.vector_store import build_metadata_filter, get_document_collection


class RetrievalAgent:
    def __init__(self) -> None:
        self.model = load_embedding_model()
        self.collection = get_document_collection()

    def retrieve_relevant_chunks(
        self, query: str, user_id: int, top_k: int = 4, document_id: int | None = None
    ) -> list[dict]:
        query_embeddings = self.model.encode([query])
        if hasattr(query_embeddings, "tolist"):
            query_embeddings = query_embeddings.tolist()
        query_embedding = query_embeddings[0]
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, min(top_k, 3)),
            where=build_metadata_filter(user_id, document_id),
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        response = []
        for idx, text in enumerate(documents):
            metadata = metadatas[idx] if idx < len(metadatas) else {}
            response.append({"text": text, **metadata})
        return response
