import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "kubernetes/apps/infra-cluster/monitoring/pbs-exporter/config/task_exporter.py"
SPEC = importlib.util.spec_from_file_location("pbs_task_exporter", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TaskOutcomeTests(unittest.TestCase):
    def test_newer_success_clears_older_failure_even_when_unordered(self):
        tasks = [
            {"worker_type": "backup", "worker_id": "home-dc:vm/4090", "endtime": 200, "status": "OK"},
            {"worker_type": "backup", "worker_id": "home-dc:vm/4090", "endtime": 100, "status": "failed"},
        ]
        self.assertEqual(MODULE.summarize(tasks), {("backup", "home-dc:vm/4090"): (200, "success")})

    def test_latest_failure_and_warning_are_distinct_per_task(self):
        tasks = [
            {"worker_type": "backup", "worker_id": "vm/1", "endtime": 100, "status": "OK"},
            {"worker_type": "backup", "worker_id": "vm/1", "endtime": 200, "status": "connection failed"},
            {"worker_type": "prune", "worker_id": "vm/1", "endtime": 300, "status": "WARNINGS: 1"},
        ]
        self.assertEqual(MODULE.summarize(tasks), {("backup", "vm/1"): (200, "error"), ("prune", "vm/1"): (300, "warning")})

    def test_running_and_irrelevant_tasks_do_not_replace_completed_backup(self):
        tasks = [
            {"worker_type": "backup", "worker_id": "vm/1", "endtime": 100, "status": "OK"},
            {"worker_type": "backup", "worker_id": "vm/1", "status": "running"},
            {"worker_type": "aptupdate", "worker_id": "", "endtime": 300, "status": "failed"},
        ]
        self.assertEqual(MODULE.summarize(tasks), {("backup", "vm/1"): (100, "success")})


if __name__ == "__main__":
    unittest.main()
