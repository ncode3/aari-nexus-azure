from __future__ import annotations

import argparse
import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.student_report_flow import (
    build_week_two_analytics,
    parse_data_center_report,
    parse_scholar_cohort_report,
    serialize_report,
)

ANALYTICS_PATH = "analytics/student-outcomes/2026/week-02-summary.json"
REPORT_PATH = (
    "reports/student-progress/david_mykel_taylor_scholars/2026/week-02/"
    "cohort-summary.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate Week 2 student analytics")
    parser.add_argument("--downloads", type=Path, default=Path("~/Downloads").expanduser())
    parser.add_argument("--account-url", default=os.getenv("AZURE_STORAGE_ACCOUNT_URL"))
    parser.add_argument("--container", default=os.getenv("AZURE_STORAGE_CONTAINER", "artifacts"))
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    cohort = parse_scholar_cohort_report(args.downloads / "cohort-progress-report.pdf")
    data_center = parse_data_center_report(args.downloads / "Progress Report 2.pdf")
    output = build_week_two_analytics(cohort, data_center)
    payload = serialize_report(output)
    if args.upload:
        if not args.account_url:
            raise ValueError("--account-url or AZURE_STORAGE_ACCOUNT_URL is required")
        container = BlobServiceClient(
            account_url=args.account_url, credential=DefaultAzureCredential()
        ).get_container_client(args.container)
        metadata = {
            "document_type": "student_outcomes_weekly_summary",
            "week_number": "2",
            "sensitivity": "internal",
            "contains_student_data": "true",
            "public_access": "false",
            "index_allowed": "false",
        }
        for path in (ANALYTICS_PATH, REPORT_PATH):
            container.upload_blob(
                path,
                payload,
                overwrite=True,
                content_settings=ContentSettings(content_type="application/json"),
                metadata=metadata,
            )
    print(
        {
            "analytics_path": ANALYTICS_PATH,
            "report_path": REPORT_PATH,
            "verified_hours": output["scholar_cohort"]["cumulative_through_week_2"][
                "verified_hours"
            ],
            "data_center_verified_hours": output["data_center_cohort"]["verified_hours"],
        }
    )


if __name__ == "__main__":
    main()

