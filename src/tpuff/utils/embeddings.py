"""Embedding generation utilities using sentence-transformers."""

import sys
from typing import Any

from rich.console import Console

console = Console(stderr=True)


class EmbeddingGenerator:
    """Embedding generator class with model caching."""

    def __init__(self) -> None:
        self._model_cache: dict[str, Any] = {}

    def generate_embedding(self, text: str, model_id: str) -> list[float]:
        """Generate an embedding for the given text using the specified model.

        Args:
            text: The text to embed.
            model_id: HuggingFace model ID (e.g., 'sentence-transformers/all-MiniLM-L6-v2').

        Returns:
            List of floats representing the embedding vector.
        """
        model = self._load_model(model_id)
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def _load_model(self, model_id: str) -> Any:
        """Load a model, using cache if available.

        Args:
            model_id: HuggingFace model ID.

        Returns:
            Loaded SentenceTransformer model.
        """
        if model_id in self._model_cache:
            return self._model_cache[model_id]

        console.print(f"Loading model: {model_id}...", style="dim")

        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_id, trust_remote_code=True)
        except Exception as e:
            console.print(f"[red]Error loading model {model_id}: {e}[/red]")
            sys.exit(1)

        self._model_cache[model_id] = model
        console.print("Model loaded successfully.", style="dim")

        return model

    def clear_cache(self) -> None:
        """Clear the model cache."""
        self._model_cache.clear()


# Singleton instance
embedding_generator = EmbeddingGenerator()
