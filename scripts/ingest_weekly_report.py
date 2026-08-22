from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.weekly_report_ingestion import (
    AHMED_PROCESSED_BLOB,
    AHMED_RAW_BLOB,
    parse_ahmed_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest an internal supplemental weekly report.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    record = parse_ahmed_report(args.input)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=2) + "\n")
    if args.upload:
        account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
        if not account_url:
            raise ValueError("AZURE_STORAGE_ACCOUNT_URL is required")
        container = BlobServiceClient(
            account_url=account_url, credential=DefaultAzureCredential()
        ).get_container_client(os.getenv("AZURE_STORAGE_CONTAINER", "artifacts"))
        metadata = {
            "document_type": "weekly_progress_report",
            "cohort": record["cohort_id"],
            "student_id": record["student_id"],
            "week_number": "1",
            "sensitivity": "internal",
            "contains_student_data": "true",
            "public_access": "false",
            "index_allowed": "false",
            "sha256": record["source_sha256"],
            "approval_status": "incomplete",
        }
        container.upload_blob(
            AHMED_RAW_BLOB,
            args.input.expanduser().read_bytes(),
            overwrite=True,
            metadata=metadata,
            content_settings=ContentSettings(
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        )
        container.upload_blob(
            AHMED_PROCESSED_BLOB,
            json.dumps(record, indent=2).encode(),
            overwrite=True,
            metadata={**metadata, "schema_version": "1.0"},
            content_settings=ContentSettings(content_type="application/json"),
        )
    print(json.dumps({
        "source_blob_path": AHMED_RAW_BLOB,
        "processed_blob_path": AHMED_PROCESSED_BLOB,
        "evidence_count": record["evidence_count"],
        "missing_fields": record["missing_fields"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
