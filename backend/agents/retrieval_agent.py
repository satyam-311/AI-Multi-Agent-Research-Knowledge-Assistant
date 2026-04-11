from services.embedding_backend import load_embedding_model
from services.vector_store import search_similar_chunks


class RetrievalAgent:
    def __init__(self) -> None:
        self.model = load_embedding_model()

    def retrieve_relevant_chunks(
        self, query: str, user_id: int, top_k: int = 4, document_id: int | None = None
    ) -> list[dict]:
        query_embedding = self.model.get_embedding(query)
        return search_similar_chunks(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=top_k,
            document_id=document_id,
        )
