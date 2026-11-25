"""One provider/model identity must be used for both indexing and queries."""
from collections.abc import Sequence
from functools import lru_cache
from google import genai
from google.genai import types
from app.core.config import Settings


class GeminiEmbeddings:
    def __init__(self, settings: Settings):
        if not settings.google_api_key.get_secret_value():
            raise ValueError("GOOGLE_API_KEY is required for Gemini embeddings")
        self.model = settings.gemini_embedding_model or "gemini-embedding-001"
        self.client = genai.Client(api_key=settings.google_api_key.get_secret_value())

    def embed(self, texts: Sequence[str], task_type: str) -> list[list[float]]:
        result = self.client.models.embed_content(
            model=self.model, contents=list(texts),
            config=types.EmbedContentConfig(task_type=task_type),
        )
        if not result.embeddings or len(result.embeddings) != len(texts):
            raise RuntimeError("Embedding provider returned incomplete results")
        return [list(item.values or []) for item in result.embeddings]


class LocalEmbeddings:
    def __init__(self, settings: Settings):
        self.model = settings.local_embedding_model
        self.encoder = _local_encoder(self.model)

    def embed(self, texts: Sequence[str], task_type: str) -> list[list[float]]:
        return self.encoder.encode(list(texts), normalize_embeddings=True).tolist()


def selected(settings: Settings):
    return GeminiEmbeddings(settings) if settings.embedding_provider == "gemini" else LocalEmbeddings(settings)


@lru_cache(maxsize=2)
def _local_encoder(model: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model)
