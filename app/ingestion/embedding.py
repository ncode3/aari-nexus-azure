from typing import Protocol


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DisabledEmbeddingProvider:
    model_name = "disabled"

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embeddings are disabled; configure an approved provider explicitly")

