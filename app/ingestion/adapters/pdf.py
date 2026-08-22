from io import BytesIO
from typing import Any

from pypdf import PdfReader


class PdfAdapter:
    content_types = frozenset({"application/pdf"})

    def parse(self, content: bytes) -> dict[str, Any]:
        reader = PdfReader(BytesIO(content))
        return {
            "page_count": len(reader.pages),
            "pages": [
                {"page_number": index, "text": page.extract_text() or ""}
                for index, page in enumerate(reader.pages, start=1)
            ],
            "pdf_metadata": {
                str(key).lstrip("/"): str(value)
                for key, value in (reader.metadata or {}).items()
            },
        }

    def normalize(self, parsed: dict[str, Any], metadata: dict[str, Any]):
        return parsed

