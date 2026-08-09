from __future__ import annotations

import argparse
import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.student_report_flow import (
    build_week_three_analytics,
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
WEEK_3_ANALYTICS_PATH = "analytics/student-outcomes/2026/week-03-summary.json"
WEEK_3_REPORT_PATH = (
    "reports/student-progress/david_mykel_taylor_scholars/2026/week-03/"
    "cohort-summary.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate Week 2 student analytics")
    parser.add_argument("--downloads", type=Path, default=Path("~/Downloads").expanduser())
    parser.add_argument("--account-url", default=os.getenv("AZURE_STORAGE_ACCOUNT_URL"))
    parser.add_argument("--container", default=os.getenv("AZURE_STORAGE_CONTAINER", "artifacts"))
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--week-number", type=int, choices=[2, 3], default=2)
    args = parser.parse_args()
    if args.week_number == 3:
        cohort = parse_scholar_cohort_report(
            args.downloads / "cohort-progress-report (1).pdf"
        )
        output = build_week_three_analytics(cohort)
        output_paths = (WEEK_3_ANALYTICS_PATH, WEEK_3_REPORT_PATH)
    else:
        cohort = parse_scholar_cohort_report(args.downloads / "cohort-progress-report.pdf")
        data_center = parse_data_center_report(args.downloads / "Progress Report 2.pdf")
        output = build_week_two_analytics(cohort, data_center)
        output_paths = (ANALYTICS_PATH, REPORT_PATH)
    payload = serialize_report(output)
    if args.upload:
        if not args.account_url:
            raise ValueError("--account-url or AZURE_STORAGE_ACCOUNT_URL is required")
        container = BlobServiceClient(
            account_url=args.account_url, credential=DefaultAzureCredential()
        ).get_container_client(args.container)
        metadata = {
            "document_type": "student_outcomes_weekly_summary",
            "week_number": str(args.week_number),
            "sensitivity": "internal",
            "contains_student_data": "true",
            "public_access": "false",
            "index_allowed": "false",
        }
        for path in output_paths:
            container.upload_blob(
                path,
                payload,
                overwrite=True,
                content_settings=ContentSettings(content_type="application/json"),
                metadata=metadata,
            )
    print(
        {
            "analytics_path": output_paths[0],
            "report_path": output_paths[1],
            "verified_hours": (
                output["cumulative_through_week_3"]["verified_hours"]
                if args.week_number == 3
                else output["scholar_cohort"]["cumulative_through_week_2"][
                    "verified_hours"
                ]
            ),
        }
    )


if __name__ == "__main__":
    main()
