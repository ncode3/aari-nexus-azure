from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit an Azure-staged file to AARI")
    parser.add_argument("file", type=Path)
    parser.add_argument("--source-system", default="azure_workflow")
    parser.add_argument("--source-identifier", required=True)
    parser.add_argument("--classification", default="internal")
    args = parser.parse_args()
    base_url = os.environ.get("AZURE_SUBMISSION_API_URL", "http://localhost:8000").rstrip("/")
    token = os.environ.get("AZURE_SUBMISSION_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    content_type = mimetypes.guess_type(args.file.name)[0] or "application/octet-stream"
    with args.file.open("rb") as handle:
        response = httpx.post(
            f"{base_url}/api/v1/documents",
            headers=headers,
            data={
                "source_system": args.source_system,
                "source_identifier": args.source_identifier,
                "classification": args.classification,
            },
            files={"file": (args.file.name, handle, content_type)},
            timeout=120,
        )
    response.raise_for_status()
    result = response.json()
    job_id = result["ingestion_job_id"]
    while True:
        status = httpx.get(
            f"{base_url}/api/v1/ingestion/jobs/{job_id}", headers=headers, timeout=30
        )
        status.raise_for_status()
        payload = status.json()
        if payload["status"] in {"completed", "failed"}:
            print(json.dumps(payload, indent=2))
            break
        time.sleep(2)


if __name__ == "__main__":
    main()

