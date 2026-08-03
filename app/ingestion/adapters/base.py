from typing import Any, Protocol


class IngestionAdapter(Protocol):
    content_types: frozenset[str]

    def parse(self, content: bytes) -> Any: ...

    def normalize(self, parsed: Any, metadata: dict[str, Any]) -> Any: ...

