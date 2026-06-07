from __future__ import annotations

from src.embeddings.base import EmbedderUnavailableError


DEFAULT_SENTENCE_TRANSFORMER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceTransformerEmbedder:
    """Optional sentence-transformers embedding backend."""

    def __init__(self, model_name: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL) -> None:
        self._model_name = model_name
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as error:
            msg = (
                "sentence-transformers is not available. Install it and ensure "
                "the embedding model can be loaded, or use keyword retrieval."
            )
            raise EmbedderUnavailableError(msg) from error

        try:
            self._model = SentenceTransformer(model_name)
        except Exception as error:
            msg = (
                f"Could not load embedding model {model_name!r}. "
                "Use keyword retrieval or check model availability."
            )
            raise EmbedderUnavailableError(msg) from error
        print(f"embedding_model_loaded model={model_name} dimension={self.dimension}")

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int | None:
        dimension = getattr(self._model, "get_embedding_dimension", None)
        if callable(dimension):
            return int(dimension())
        dimension = getattr(self._model, "get_sentence_embedding_dimension", None)
        if callable(dimension):
            return int(dimension())
        return None

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return [embedding.tolist() for embedding in embeddings]
