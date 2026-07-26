from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


TECHNICAL_SKILLS_HEADERS = {
    "timestamp": "Timestamp",
    "linux": "How much Linux experience do you have?",
    "command_line": "How much command line experience do you have?",
    "public_cloud": "Have you ever used a Public Cloud (AWS, GCP, Azure, etc.)?",
    "server_build": "Have you ever created a virtual machine or built a bare metal server?",
    "networking": "Are you familiar with networking concepts like VLAN, IP addresses, subnets?",
    "job_ready": "Do you feel ready to enter the job market?",
}

VALID_STAGES = {"baseline", "midpoint", "final", "follow-up"}


@dataclass(frozen=True)
class AssessmentMetadata:
    cohort_slug: str
    assessment_stage: str
    instrument_version: str
    source_file_name: str
    participant_id_column: str | None = None
    program_slug: str = "technical-skills"

    def validate(self) -> None:
        if self.assessment_stage not in VALID_STAGES:
            raise ValueError(f"assessment_stage must be one of {sorted(VALID_STAGES)}")
        if not self.cohort_slug.strip():
            raise ValueError("cohort_slug is required")
        if not self.instrument_version.strip():
            raise ValueError("instrument_version is required")


def _as_yes_no(value: object) -> bool:
    normalized = str(value).strip().lower()
    if normalized not in {"yes", "no"}:
        raise ValueError(f"Expected Yes/No value, received {value!r}")
    return normalized == "yes"


def _as_level(value: object, field_name: str) -> int:
    level = int(str(value).strip())
    if level < 1 or level > 5:
        raise ValueError(f"{field_name} must be between 1 and 5")
    return level


def _parse_timestamp(value: object) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("Timestamp is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _readiness_score(record: Mapping[str, Any]) -> float:
    components = [
        (record["linux_experience_level"] - 1) / 4,
        (record["command_line_experience_level"] - 1) / 4,
        float(record["public_cloud_experience"]),
        float(record["server_build_experience"]),
        float(record["networking_familiarity"]),
        float(record["job_market_ready"]),
    ]
    return round(sum(components) / len(components) * 100, 2)


def _response_id(record: Mapping[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"tsa_{hashlib.sha256(canonical).hexdigest()[:16]}"


def normalize_rows(rows: Iterable[Mapping[str, object]], metadata: AssessmentMetadata) -> dict[str, Any]:
    metadata.validate()
    normalized: list[dict[str, Any]] = []

    for row_number, row in enumerate(rows, start=2):
        try:
            record: dict[str, Any] = {
                "submitted_at": _parse_timestamp(row[TECHNICAL_SKILLS_HEADERS["timestamp"]]),
                "linux_experience_level": _as_level(row[TECHNICAL_SKILLS_HEADERS["linux"]], "Linux experience"),
                "command_line_experience_level": _as_level(
                    row[TECHNICAL_SKILLS_HEADERS["command_line"]], "Command-line experience"
                ),
                "public_cloud_experience": _as_yes_no(row[TECHNICAL_SKILLS_HEADERS["public_cloud"]]),
                "server_build_experience": _as_yes_no(row[TECHNICAL_SKILLS_HEADERS["server_build"]]),
                "networking_familiarity": _as_yes_no(row[TECHNICAL_SKILLS_HEADERS["networking"]]),
                "job_market_ready": _as_yes_no(row[TECHNICAL_SKILLS_HEADERS["job_ready"]]),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid assessment row {row_number}: {exc}") from exc

        participant_id = None
        if metadata.participant_id_column:
            participant_id = str(row.get(metadata.participant_id_column, "")).strip() or None
        record["participant_id"] = participant_id
        record["linkage_status"] = "participant-linked" if participant_id else "cohort-only"
        record["self_reported_readiness_score"] = _readiness_score(record)
        record["response_id"] = _response_id(record)
        normalized.append(record)

    if not normalized:
        raise ValueError("No assessment rows were supplied")

    submitted = sorted(item["submitted_at"] for item in normalized)
    return {
        "schema_version": "1.0",
        "assessment_type": "technical-skills-self-assessment",
        "program_slug": metadata.program_slug,
        "cohort_slug": metadata.cohort_slug,
        "assessment_stage": metadata.assessment_stage,
        "instrument_version": metadata.instrument_version,
        "source_file_name": metadata.source_file_name,
        "linkage_mode": "participant" if metadata.participant_id_column else "cohort-only",
        "assessment_window": {"start": submitted[0], "end": submitted[-1]},
        "response_count": len(normalized),
        "aggregate": build_aggregate(normalized),
        "responses": normalized,
    }


def build_aggregate(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    count = len(records)

    def mean(field: str) -> float:
        return round(sum(float(item[field]) for item in records) / count, 2)

    def percent_true(field: str) -> float:
        return round(sum(bool(item[field]) for item in records) / count * 100, 2)

    return {
        "linux_experience_mean": mean("linux_experience_level"),
        "command_line_experience_mean": mean("command_line_experience_level"),
        "public_cloud_experience_percent": percent_true("public_cloud_experience"),
        "server_build_experience_percent": percent_true("server_build_experience"),
        "networking_familiarity_percent": percent_true("networking_familiarity"),
        "job_market_ready_percent": percent_true("job_market_ready"),
        "self_reported_readiness_score_mean": mean("self_reported_readiness_score"),
    }


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_blob_paths(metadata: AssessmentMetadata, source_suffix: str = ".csv") -> dict[str, str]:
    year = metadata.instrument_version[:4]
    base = f"student-progress/{metadata.cohort_slug}/{year}/assessments/{metadata.assessment_stage}"
    return {
        "raw": f"raw/20_internal/{base}/technical-skills-assessment{source_suffix}",
        "processed": f"processed/{base}/technical-skills-assessment.json",
    }


def _blob_service_client(connection_string: str | None, account_url: str | None):
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    if connection_string:
        return BlobServiceClient.from_connection_string(connection_string)
    if account_url:
        return BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())
    raise ValueError("Set AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_URL")


def upload_assessment_package(
    *,
    raw_path: str | Path,
    package: Mapping[str, Any],
    metadata: AssessmentMetadata,
    container_name: str,
    connection_string: str | None = None,
    account_url: str | None = None,
) -> dict[str, str]:
    from azure.storage.blob import ContentSettings

    raw_file = Path(raw_path)
    paths = build_blob_paths(metadata, raw_file.suffix.lower())
    client = _blob_service_client(connection_string, account_url)
    container = client.get_container_client(container_name)

    raw_bytes = raw_file.read_bytes()
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    processed = dict(package)
    processed["ingestion"] = {
        "ingested_at": datetime.now(UTC).isoformat(),
        "raw_sha256": raw_sha256,
        "raw_blob_path": paths["raw"],
        "processed_blob_path": paths["processed"],
    }

    container.upload_blob(
        name=paths["raw"],
        data=raw_bytes,
        overwrite=True,
        content_settings=ContentSettings(content_type="text/csv"),
        metadata={"data_classification": "internal", "sha256": raw_sha256},
    )
    container.upload_blob(
        name=paths["processed"],
        data=json.dumps(processed, indent=2).encode("utf-8"),
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
        metadata={"data_classification": "internal", "schema_version": "1.0"},
    )
    return paths
