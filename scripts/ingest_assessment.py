from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.assessment_flow import (
    AssessmentMetadata,
    add_ingestion_metadata,
    normalize_rows,
    read_assessment_rows,
    upload_assessment_package,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize and upload an AARI technical skills assessment.")
    parser.add_argument("source", nargs="?", type=Path, help="CSV or XLSX assessment export")
    parser.add_argument("--input", dest="input_path", type=Path, help="CSV or XLSX assessment export")
    parser.add_argument("--cohort", required=True, help="Stable cohort slug, e.g. summer-2026-data-center")
    parser.add_argument("--stage", required=True, choices=["baseline", "midpoint", "final", "follow-up"])
    parser.add_argument("--instrument-version", required=True, help="Version date, e.g. 2026-01")
    parser.add_argument("--participant-id-column")
    parser.add_argument("--output", type=Path, help="Write normalized JSON locally")
    parser.add_argument("--upload", action="store_true", help="Upload raw and processed artifacts")
    args = parser.parse_args()
    args.input_path = (args.input_path or args.source)
    if not args.input_path:
        parser.error("provide --input or a positional source file")
    args.input_path = args.input_path.expanduser()
    return args


def main() -> None:
    args = parse_args()
    metadata = AssessmentMetadata(
        cohort_slug=args.cohort,
        assessment_stage=args.stage,
        instrument_version=args.instrument_version,
        source_file_name=args.input_path.name,
        participant_id_column=args.participant_id_column,
    )
    package = normalize_rows(read_assessment_rows(args.input_path), metadata)
    enriched = add_ingestion_metadata(package, args.input_path, metadata)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(enriched, indent=2), encoding="utf-8")
        print(args.output)
        if not args.upload:
            return

    if args.upload:
        paths = upload_assessment_package(
            raw_path=args.input_path,
            package=package,
            metadata=metadata,
            container_name=os.getenv("AZURE_STORAGE_CONTAINER", "artifacts"),
            connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING") or None,
            account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL") or None,
        )
        print(json.dumps(paths, indent=2))
    elif not args.output:
        print(json.dumps(enriched, indent=2))


if __name__ == "__main__":
    main()
