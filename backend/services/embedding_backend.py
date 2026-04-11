import os

import google.generativeai as genai

GEMINI_EMBEDDING_MODEL = "models/text-embedding-004"
GEMINI_EMBEDDING_DIMENSION = 768


class GeminiEmbedder:
    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        genai.configure(api_key=api_key)

    def get_embedding(self, text: str) -> list[float]:
        try:
            response = genai.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                content=text,
            )
            embedding = response["embedding"]
            if not isinstance(embedding, list) or not embedding:
                raise RuntimeError("Gemini returned an empty embedding.")
            return embedding
        except Exception as exc:
            raise RuntimeError(f"Embedding failed: {str(exc)}") from exc

    def encode(self, texts: list[str] | tuple[str, ...]) -> list[list[float]]:
        return [self.get_embedding(text) for text in texts]


def get_embedding(text: str) -> list[float]:
    return GeminiEmbedder().get_embedding(text)


def load_embedding_model():
    return GeminiEmbedder()
