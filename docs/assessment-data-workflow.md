# Technical Skills Assessment Data Workflow

## Purpose

Technical skills surveys are longitudinal program evidence. The workflow preserves the private source export, creates a normalized JSON record, and supports baseline-to-midpoint-to-final comparisons.

## Azure paths

For cohort `summer-2026-data-center`, year `2026`, and stage `baseline`:

```text
raw/20_internal/student-progress/summer-2026-data-center/2026/assessments/baseline/technical-skills-assessment.xlsx
processed/student-progress/summer-2026-data-center/2026/assessments/baseline/technical-skills-assessment.json
```

The raw object stays private. The processed object contains normalized responses, aggregate metrics, source hash, schema version, and linkage status.

## Required survey fields going forward

Every assessment should include:

1. `AARI Student ID`: a stable AARI-issued ID, not an email address.
2. Assessment stage: baseline, midpoint, final, or follow-up.
3. Cohort: a stable cohort slug supplied at ingestion.
4. The same scored questions and 1-to-5 scales across each assessment window.

Without an AARI Student ID, this workflow can measure cohort-level change only. It cannot prove how an individual student changed.

Future forms should preserve the exact scored question text and add an `AARI Student ID`
column. Pass `--participant-id-column "AARI Student ID"` at every stage. Baseline-to-midpoint
and baseline-to-final change is calculated by subtracting each baseline aggregate from the later
aggregate. Individual change is calculated only when the same stable student ID occurs at both
stages; anonymous responses are never probabilistically matched.

## Ingestion

Export Google Forms responses as CSV or XLSX. Uploading is an explicit operation:

```bash
python scripts/ingest_assessment.py \
  --input "~/Downloads/Technical Skills Assessment Survey (Responses).xlsx" \
  --cohort summer-2026-data-center \
  --stage baseline \
  --instrument-version 2026-01 \
  --upload
```

To validate locally without uploading:

```bash
python scripts/ingest_assessment.py \
  --input "~/Downloads/Technical Skills Assessment Survey (Responses).xlsx" \
  --cohort summer-2026-data-center \
  --stage baseline \
  --instrument-version 2026-01 \
  --output ./technical-skills-baseline.json
```

Authentication uses either:

- `AZURE_STORAGE_CONNECTION_STRING`, or
- `AZURE_STORAGE_ACCOUNT_URL` with `DefaultAzureCredential`.

The default container is `artifacts`.

## Comparison metrics

Track these at baseline, midpoint, and final:

- mean Linux experience level
- mean command-line experience level
- percentage with public-cloud experience
- percentage with VM or bare-metal build experience
- percentage familiar with networking concepts
- percentage reporting job-market readiness
- mean self-reported readiness score

The readiness score equally weights the six survey domains after normalizing the two 1-to-5 scales. It is a self-reported program indicator, not an objective certification or performance exam.

## Existing January 2026 file

The January export contains 33 anonymous responses and no participant identifier. Its baseline metrics are:

- Linux experience: 1.73 / 5
- command-line experience: 2.45 / 5
- public-cloud experience: 30.30%
- server-build experience: 30.30%
- networking familiarity: 42.42%
- job-market readiness: 21.21%
- composite self-reported readiness: 29.80 / 100

Ingest it with `linkage_mode=cohort-only`. Before assigning it to a named cohort, document which cohort the respondents represent.
