import base64
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "scripts/bootstrap-postgres-backup.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_postgres_backup", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AWXRecoveryCredentialsTest(unittest.TestCase):
    def test_conflicting_recovery_password_is_not_overwritten(self):
        writes = []

        def call(args, value=None):
            if args[0] == "kubectl":
                fields = {
                    "username": "awx",
                    "database": "awx",
                    "host": "awx-postgres-15",
                    "port": "5432",
                    "password": "live-password",
                }
                return json.dumps({"data": {k: base64.b64encode(v.encode()).decode() for k, v in fields.items()}})
            if args[1:3] == ["secrets", "get"]:
                key = args[3]
                return json.dumps({key: {"computed": "saved-key" if key == "AWX_SECRET_KEY" else "old-password"}})
            writes.append((args, value))
            raise AssertionError("conflicting recovery password must never be written")

        with patch.object(MODULE, "captured", side_effect=call):
            with self.assertRaisesRegex(RuntimeError, "refusing overwrite"):
                MODULE.ensure_awx_recovery(["kubectl"], [], {"AWX_SECRET_KEY", "AWX_DB_PASSWORD"})
        self.assertEqual(writes, [])

    def test_missing_awx_encryption_key_stops_before_reading_or_writing(self):
        with patch.object(MODULE, "captured") as call:
            with self.assertRaisesRegex(RuntimeError, "AWX_SECRET_KEY is missing"):
                MODULE.ensure_awx_recovery(["kubectl"], [], set())
        call.assert_not_called()

    def test_unexpected_database_identity_is_rejected(self):
        calls = []

        def call(args, value=None):
            calls.append(args)
            if args[0] == "kubectl":
                fields = {"username": "wrong", "database": "awx", "host": "awx-postgres-15", "port": "5432"}
                return json.dumps({"data": {k: base64.b64encode(v.encode()).decode() for k, v in fields.items()}})
            return json.dumps({"AWX_SECRET_KEY": {"computed": "saved-key"}})

        with patch.object(MODULE, "captured", side_effect=call):
            with self.assertRaisesRegex(RuntimeError, "Unexpected AWX database username"):
                MODULE.ensure_awx_recovery(["kubectl"], [], {"AWX_SECRET_KEY"})
        self.assertFalse(any(a[1:3] == ["secrets", "set"] for a in calls))


if __name__ == "__main__":
    unittest.main()
