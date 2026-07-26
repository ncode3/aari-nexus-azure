from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.assessment_flow import AssessmentMetadata, normalize_rows, read_csv_rows, upload_assessment_package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize and upload an AARI technical skills assessment.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--cohort", required=True, help="Stable cohort slug, e.g. summer-2026-data-center")
    parser.add_argument("--stage", required=True, choices=["baseline", "midpoint", "final", "follow-up"])
    parser.add_argument("--instrument-version", required=True, help="Version date, e.g. 2026-01")
    parser.add_argument("--participant-id-column")
    parser.add_argument("--output", type=Path, help="Write normalized JSON locally instead of uploading")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = AssessmentMetadata(
        cohort_slug=args.cohort,
        assessment_stage=args.stage,
        instrument_version=args.instrument_version,
        source_file_name=args.csv_path.name,
        participant_id_column=args.participant_id_column,
    )
    package = normalize_rows(read_csv_rows(args.csv_path), metadata)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(package, indent=2), encoding="utf-8")
        print(args.output)
        return

    paths = upload_assessment_package(
        raw_path=args.csv_path,
        package=package,
        metadata=metadata,
        container_name=os.getenv("AZURE_STORAGE_CONTAINER", "artifacts"),
        connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING") or None,
        account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL") or None,
    )
    print(json.dumps(paths, indent=2))


if __name__ == "__main__":
    main()
