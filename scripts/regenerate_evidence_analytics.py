from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.evidence_analytics import (
    BASELINE_SOURCE,
    COURSERA_SOURCE,
    WEEK1_SOURCE,
    build_baseline_summary,
    build_reporting_completeness,
    build_student_outcomes,
    enhance_coursera,
)

BASELINE_SUMMARY = "analytics/assessments/technical-skills/2026/baseline-summary.json"
REPORTING_COMPLETENESS = (
    "processed/reporting-completeness/david_mykel_taylor_scholars/2026/week-01.json"
)
STUDENT_OUTCOMES = "analytics/student-outcomes/2026/student-outcomes-v2.json"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Regenerate AARI private evidence analytics.")
    value.add_argument("--output-dir", type=Path)
    value.add_argument("--upload", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
    if not account_url:
        raise ValueError("AZURE_STORAGE_ACCOUNT_URL is required")
    service = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())
    container = service.get_container_client(os.getenv("AZURE_STORAGE_CONTAINER", "artifacts"))

    def read(name: str) -> dict:
        return json.loads(container.get_blob_client(name).download_blob().readall())

    week = read(WEEK1_SOURCE)
    baseline = read(BASELINE_SOURCE)
    coursera = read(COURSERA_SOURCE)
    outputs = {
        BASELINE_SUMMARY: build_baseline_summary(baseline),
        REPORTING_COMPLETENESS: build_reporting_completeness(week),
        STUDENT_OUTCOMES: build_student_outcomes(week, baseline, coursera),
        COURSERA_SOURCE: enhance_coursera(coursera),
    }
    if args.output_dir:
        for blob_path, record in outputs.items():
            destination = args.output_dir / blob_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(record, indent=2) + "\n")
    if args.upload:
        metadata = {
            "sensitivity": "internal",
            "contains_student_data": "true",
            "public_access": "false",
            "index_allowed": "false",
            "schema_version": "2.0",
        }
        for blob_path, record in outputs.items():
            container.upload_blob(
                blob_path,
                json.dumps(record, indent=2).encode(),
                overwrite=True,
                metadata=metadata,
                content_settings=ContentSettings(content_type="application/json"),
            )
    print(json.dumps({
        "outputs": list(outputs),
        "baseline_responses": baseline["response_count"],
        "week1_expected": outputs[REPORTING_COMPLETENESS]["metrics"]["expected_reports"]["value"],
        "week1_submitted": outputs[REPORTING_COMPLETENESS]["metrics"]["submitted_reports"]["value"],
        "week1_verified_hours": outputs[REPORTING_COMPLETENESS]["metrics"]["verified_hours"]["value"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
