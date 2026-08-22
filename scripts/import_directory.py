from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

from app.db.session import SessionLocal
from app.ingestion.adapters import CsvAdapter, JsonAdapter, PdfAdapter, XlsxAdapter
from app.ingestion.pipeline import IngestionPipeline, IngestionRequest
from app.services.object_store import MinioObjectStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import one file or a directory into AARI")
    parser.add_argument("path", type=Path)
    parser.add_argument("--source-system", default="local_directory")
    parser.add_argument("--classification", choices=["public", "internal", "restricted"], default="internal")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.path.expanduser().resolve()
    files = [source] if source.is_file() else sorted(item for item in source.rglob("*") if item.is_file())
    with SessionLocal() as session:
        pipeline = IngestionPipeline(
            session,
            MinioObjectStore(),
            [CsvAdapter(), XlsxAdapter(), JsonAdapter(), PdfAdapter()],
        )
        for path in files:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            try:
                result = pipeline.ingest(
                    IngestionRequest(
                        filename=path.name,
                        content_type=content_type,
                        content=path.read_bytes(),
                        source_system=args.source_system,
                        source_identifier=str(path),
                        classification=args.classification,
                    )
                )
                print(f"{path}: {result.status} {result.document_id}")
            except ValueError as exc:
                print(f"{path}: rejected ({exc})")


if __name__ == "__main__":
    main()

