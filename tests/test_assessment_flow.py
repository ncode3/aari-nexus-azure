from __future__ import annotations

import unittest

from app.assessment_flow import AssessmentMetadata, build_blob_paths, normalize_rows


class AssessmentFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = AssessmentMetadata(
            cohort_slug="summer-2026-data-center",
            assessment_stage="baseline",
            instrument_version="2026-01",
            source_file_name="technical-skills.csv",
        )
        self.rows = [
            {
                "Timestamp": "2026-01-03T11:44:55",
                "How much Linux experience do you have?": "1",
                "How much command line experience do you have?": "2",
                "Have you ever used a Public Cloud (AWS, GCP, Azure, etc.)?": "Yes",
                "Have you ever created a virtual machine or built a bare metal server?": "No",
                "Are you familiar with networking concepts like VLAN, IP addresses, subnets?": "Yes",
                "Do you feel ready to enter the job market?": "No",
            },
            {
                "Timestamp": "2026-01-04T11:44:55",
                "How much Linux experience do you have?": "3",
                "How much command line experience do you have?": "4",
                "Have you ever used a Public Cloud (AWS, GCP, Azure, etc.)?": "No",
                "Have you ever created a virtual machine or built a bare metal server?": "Yes",
                "Are you familiar with networking concepts like VLAN, IP addresses, subnets?": "No",
                "Do you feel ready to enter the job market?": "Yes",
            },
        ]

    def test_normalizes_and_aggregates(self) -> None:
        package = normalize_rows(self.rows, self.metadata)
        self.assertEqual(package["response_count"], 2)
        self.assertEqual(package["assessment_stage"], "baseline")
        self.assertEqual(package["linkage_mode"], "cohort-only")
        self.assertEqual(package["aggregate"]["linux_experience_mean"], 2.0)
        self.assertEqual(package["aggregate"]["job_market_ready_percent"], 50.0)
        self.assertTrue(package["responses"][0]["response_id"].startswith("tsa_"))

    def test_blob_paths_separate_stages(self) -> None:
        paths = build_blob_paths(self.metadata)
        self.assertEqual(
            paths["processed"],
            "processed/student-progress/summer-2026-data-center/2026/assessments/baseline/technical-skills-assessment.json",
        )
        self.assertTrue(paths["raw"].startswith("raw/20_internal/"))

    def test_rejects_invalid_level(self) -> None:
        self.rows[0]["How much Linux experience do you have?"] = "6"
        with self.assertRaisesRegex(ValueError, "between 1 and 5"):
            normalize_rows(self.rows, self.metadata)

    def test_participant_linkage_when_column_exists(self) -> None:
        metadata = AssessmentMetadata(
            cohort_slug="summer-2026-data-center",
            assessment_stage="final",
            instrument_version="2026-09",
            source_file_name="technical-skills-final.csv",
            participant_id_column="AARI Student ID",
        )
        for index, row in enumerate(self.rows, start=1):
            row["AARI Student ID"] = f"AARI-{index:04d}"
        package = normalize_rows(self.rows, metadata)
        self.assertEqual(package["linkage_mode"], "participant")
        self.assertEqual(package["responses"][0]["participant_id"], "AARI-0001")


if __name__ == "__main__":
    unittest.main()
