# Evidence Analytics v2

The v2 evidence model separates reported indicators from proven outcomes. Every aggregate
metric carries an evidence status, source Blob path, and update timestamp.

## Live outputs

```text
analytics/assessments/technical-skills/2026/baseline-summary.json
processed/reporting-completeness/david_mykel_taylor_scholars/2026/week-01.json
analytics/student-outcomes/2026/student-outcomes-v2.json
processed/learning-platforms/coursera/aari-google-learning-program/2026/learner-roster.json
```

Regenerate them with:

```bash
AZURE_STORAGE_ACCOUNT_URL=https://<account>.blob.core.windows.net \
AZURE_STORAGE_CONTAINER=artifacts \
python scripts/regenerate_evidence_analytics.py --upload
```

## Evidence quality

Weekly activities use `reported_only`, `evidence_submitted`, `mentor_verified`, or
`completed`. A narrative is always `reported_only` unless a separate artifact or verifier is
recorded. URLs are not treated as completed work, and an artifact hash remains null until the
artifact itself is retrieved and hashed.

## Longitudinal skills

The model supports baseline, midpoint, and final self-assessment, objective assessment, and
mentor assessment values for Linux, command line, cloud, networking, server hardware,
data-center operations, cybersecurity, robotics, ROS, and career readiness. Change values stay
null until both required stages exist.

## Private outcome records

The internal model supports practical competencies, versioned career-readiness records,
student-to-GitHub identity mappings, contribution types, Coursera progress and certificates,
employment outcomes, and sponsor attribution. Unknown values remain null. Sponsor-facing
outputs are aggregate-only unless individual consent is documented.
