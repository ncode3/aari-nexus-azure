from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.student_report_flow import (
    ReportRoute,
    parse_data_center_report,
    parse_individual_progress_log,
    parse_scholar_cohort_report,
    serialize_report,
)


def upload_idempotent(container, path: str, payload: bytes, content_type: str, metadata: dict):
    blob = container.get_blob_client(path)
    if blob.exists():
        properties = blob.get_blob_properties()
        if properties.metadata.get("sha256") == metadata["sha256"]:
            return "duplicate"
        raise ValueError(f"Blob path already exists with a different checksum: {path}")
    blob.upload_blob(
        payload,
        overwrite=False,
        content_settings=ContentSettings(content_type=content_type),
        metadata=metadata,
    )
    return "uploaded"


def routes(
    downloads: Path,
) -> list[tuple[Path, ReportRoute, Callable[[Path], dict[str, Any]]]]:
    return [
        (
            downloads / "cohort-progress-report.pdf",
            ReportRoute(
                "raw/20_internal/student-progress/david_mykel_taylor_scholars/2026/"
                "week-02/cohort-progress-report.pdf",
                "processed/student-progress/david_mykel_taylor_scholars/2026/"
                "week-02/cohort-progress-report.json",
                "david_mykel_taylor_scholars",
                2,
                "cohort_progress_report",
            ),
            parse_scholar_cohort_report,
        ),
        (
            downloads / "rasheed-jeheeb-progress-log (1).pdf",
            ReportRoute(
                "raw/20_internal/student-progress/david_mykel_taylor_scholars/2026/"
                "week-02/individual/rasheed-jeheeb-progress-log.pdf",
                "processed/student-progress/david_mykel_taylor_scholars/2026/"
                "week-02/individual/rasheed-jeheeb-progress-log.json",
                "david_mykel_taylor_scholars",
                2,
                "individual_progress_log",
            ),
            parse_individual_progress_log,
        ),
        (
            downloads / "rasheed-jeheeb-progress-log.pdf",
            ReportRoute(
                "raw/20_internal/student-progress/david_mykel_taylor_scholars/2026/"
                "week-02/source-versions/rasheed-jeheeb-progress-log-superseded-4-days.pdf",
                None,
                "david_mykel_taylor_scholars",
                2,
                "individual_progress_log",
                "superseded",
            ),
            parse_individual_progress_log,
        ),
        (
            downloads / "Progress Report 2.pdf",
            ReportRoute(
                "raw/20_internal/student-progress/summer-2026-data-center/2026/"
                "week-02/progress-report-2.pdf",
                "processed/student-progress/summer-2026-data-center/2026/"
                "week-02/progress-report-2.json",
                "summer_2026_data_center",
                2,
                "data_center_progress_report",
            ),
            parse_data_center_report,
        ),
        (
            downloads / "cohort-progress-report (1).pdf",
            ReportRoute(
                "raw/20_internal/student-progress/david_mykel_taylor_scholars/2026/"
                "week-03/cohort-progress-report.pdf",
                "processed/student-progress/david_mykel_taylor_scholars/2026/"
                "week-03/cohort-progress-report.json",
                "david_mykel_taylor_scholars",
                3,
                "cohort_progress_report",
            ),
            parse_scholar_cohort_report,
        ),
        (
            downloads / "rasheed-jeheeb-progress-log (3).pdf",
            ReportRoute(
                "raw/20_internal/student-progress/david_mykel_taylor_scholars/2026/"
                "week-03/individual/rasheed-jeheeb-progress-log.pdf",
                "processed/student-progress/david_mykel_taylor_scholars/2026/"
                "week-03/individual/rasheed-jeheeb-progress-log.json",
                "david_mykel_taylor_scholars",
                3,
                "individual_progress_log",
            ),
            parse_individual_progress_log,
        ),
        (
            downloads / "Progress Report 3.pdf",
            ReportRoute(
                "raw/20_internal/student-progress/summer-2026-data-center/2026/"
                "week-03/progress-report-3.pdf",
                "processed/student-progress/summer-2026-data-center/2026/"
                "week-03/progress-report-3.json",
                "summer_2026_data_center",
                3,
                "data_center_progress_report",
            ),
            parse_data_center_report,
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest downloaded AARI student reports")
    parser.add_argument("--downloads", type=Path, default=Path("~/Downloads").expanduser())
    parser.add_argument("--account-url", default=os.getenv("AZURE_STORAGE_ACCOUNT_URL"))
    parser.add_argument("--container", default=os.getenv("AZURE_STORAGE_CONTAINER", "artifacts"))
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--week-number", type=int, choices=[2, 3])
    args = parser.parse_args()
    selected = [
        item
        for item in routes(args.downloads.expanduser())
        if args.week_number is None or item[1].week_number == args.week_number
    ]
    missing = [str(path) for path, _, _ in selected if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing report files: " + ", ".join(missing))
    client = None
    if args.upload:
        if not args.account_url:
            raise ValueError("--account-url or AZURE_STORAGE_ACCOUNT_URL is required")
        client = BlobServiceClient(
            account_url=args.account_url, credential=DefaultAzureCredential()
        ).get_container_client(args.container)
    results = []
    for source, route, parse in selected:
        package = parse(source)
        metadata = {
            "document_type": route.document_type,
            "cohort": route.cohort,
            "week_number": str(route.week_number),
            "sensitivity": "internal",
            "contains_student_data": "true",
            "public_access": "false",
            "index_allowed": "false",
            "status": route.status,
            "sha256": package["source_sha256"],
        }
        upload_status = "dry_run"
        if client:
            upload_status = upload_idempotent(
                client,
                route.raw_blob_path,
                source.read_bytes(),
                "application/pdf",
                metadata,
            )
            if route.processed_blob_path:
                processed_status = upload_idempotent(
                    client,
                    route.processed_blob_path,
                    serialize_report(package),
                    "application/json",
                    {
                        **metadata,
                        "document_type": f"{route.document_type}_normalized",
                    },
                )
                if upload_status == "duplicate" and processed_status == "uploaded":
                    upload_status = "repaired_processed_output"
        results.append(
            {
                "source": source.name,
                "sha256": package["source_sha256"],
                "raw_blob_path": route.raw_blob_path,
                "processed_blob_path": route.processed_blob_path,
                "status": route.status,
                "upload_status": upload_status,
            }
        )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
