"""Consumer-visible acceptance boundaries for the backup coverage auditor."""

import copy
import datetime as dt
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "backup_audit",
    Path(__file__).resolve().parents[1]
    / "kubernetes/components/backup-runtime/audit.py",
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 10, 30, 12, tzinfo=dt.timezone.utc)
        self.start = self.now - dt.timedelta(hours=1)
        self.repository = "/repository/app-cluster/media/critical-6h"
        self.sources = {"immich-db": {"profile": "critical-6h"}}
        self.backup = {
            "metadata": {
                "uid": "native-backup",
                "creationTimestamp": self.start.isoformat(),
            },
            "spec": {
                "backend": {"local": {"mountPath": self.repository}},
                "labelSelectors": [
                    {
                        "matchLabels": {
                            "backup.krapulax.dev/policy": "critical-6h",
                            "backup.krapulax.dev/strategy": "postgres-dump",
                        }
                    }
                ],
            },
            "status": {
                "finished": True,
                "conditions": [
                    {"type": "Completed", "status": "True", "reason": "Succeeded"}
                ],
            },
        }
        self.job = {
            "metadata": {"ownerReferences": [{"uid": "native-backup"}]},
            "status": {
                "succeeded": 1,
                "completionTime": (self.start + dt.timedelta(seconds=20)).isoformat(),
            },
        }
        self.snapshot = {
            "spec": {
                "id": "a" * 64,
                "repository": self.repository,
                "paths": ["/media-immich-db.tar"],
                "date": (self.start + dt.timedelta(seconds=10)).isoformat(),
            }
        }

    def evaluate(self, backups=None, jobs=None, snapshots=None, sources=None, now=None):
        return audit.coverage(
            self.sources if sources is None else sources,
            [self.backup] if backups is None else backups,
            [self.job] if jobs is None else jobs,
            [self.snapshot] if snapshots is None else snapshots,
            "media",
            self.repository,
            now or self.now,
        )

    def test_fresh_capture_requires_successful_job_and_exact_snapshot(self):
        report, problems = self.evaluate()
        self.assertEqual(report["immich-db"]["snapshot"], "a" * 64)
        self.assertEqual(problems, [])

    def test_failed_producer_snapshot_is_not_accepted(self):
        self.backup["status"]["conditions"][0]["reason"] = "Failed"
        report, problems = self.evaluate()
        self.assertNotIn("immich-db", report)
        self.assertTrue(any("no successful native capture" in p for p in problems))

    def test_missing_job_provenance_is_not_accepted(self):
        report, problems = self.evaluate(jobs=[])
        self.assertNotIn("immich-db", report)
        self.assertTrue(problems)

    def test_wrong_artifact_identity_and_capture_window_are_rejected(self):
        for field, value in [
            ("paths", ["/media-litellm-db.tar"]),
            ("repository", "/another-repository"),
            ("id", "a" * 8),
            ("date", self.now.isoformat()),
        ]:
            with self.subTest(field=field):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot["spec"][field] = value
                report, problems = self.evaluate(snapshots=[snapshot])
                self.assertNotIn("immich-db", report)
                self.assertTrue(problems)

    def test_eight_hour_capture_age_boundary_is_conservative(self):
        for extra, stale in [(0, False), (1, True)]:
            with self.subTest(seconds_over_limit=extra):
                _, problems = self.evaluate(
                    now=self.start + dt.timedelta(hours=8, seconds=extra)
                )
                self.assertEqual(any("stale" in p for p in problems), stale)

    def test_zero_expected_sources_is_not_healthy(self):
        _, problems = self.evaluate(sources={})
        self.assertTrue(any("no expected sources" in p for p in problems))

    def test_wrong_app_selector_does_not_widen_to_policy(self):
        self.backup["spec"]["labelSelectors"][0]["matchLabels"][
            "backup.krapulax.dev/app"
        ] = "another-app"
        report, problems = self.evaluate()
        self.assertNotIn("immich-db", report)
        self.assertTrue(problems)

    def test_unique_one_off_selector_remains_auditable(self):
        self.backup["metadata"]["labels"] = {
            "backup.krapulax.dev/app": "immich-db",
            "backup.krapulax.dev/policy": "critical-6h",
            "backup.krapulax.dev/operation": "unique-run",
        }
        self.backup["spec"]["labelSelectors"][0]["matchLabels"][
            "backup.krapulax.dev/operation"
        ] = "unique-run"
        self.backup["metadata"]["labels"]["backup.krapulax.dev/proof-id"] = "unique-run"
        self.backup["spec"]["labelSelectors"][0]["matchLabels"][
            "backup.krapulax.dev/proof-id"
        ] = "unique-run"
        _, problems = self.evaluate()
        self.assertEqual(problems, [])

    def test_newer_failure_alerts_and_later_success_recovers(self):
        failed = copy.deepcopy(self.backup)
        failed["metadata"] = {
            "uid": "failed-backup",
            "creationTimestamp": (self.start + dt.timedelta(minutes=5)).isoformat(),
        }
        failed["status"]["conditions"][0]["reason"] = "Failed"
        _, problems = self.evaluate(backups=[self.backup, failed])
        self.assertTrue(any("newer capture failed" in p for p in problems))
        recovered = copy.deepcopy(self.backup)
        recovered["metadata"] = {
            "uid": "recovered-backup",
            "creationTimestamp": (self.start + dt.timedelta(minutes=10)).isoformat(),
        }
        recovered_job = copy.deepcopy(self.job)
        recovered_job["metadata"]["ownerReferences"][0]["uid"] = "recovered-backup"
        recovered_job["status"]["completionTime"] = (
            self.start + dt.timedelta(minutes=11)
        ).isoformat()
        recovered_snapshot = copy.deepcopy(self.snapshot)
        recovered_snapshot["spec"]["date"] = (
            self.start + dt.timedelta(minutes=10, seconds=10)
        ).isoformat()
        _, problems = self.evaluate(
            backups=[self.backup, failed, recovered],
            jobs=[self.job, recovered_job],
            snapshots=[self.snapshot, recovered_snapshot],
        )
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
