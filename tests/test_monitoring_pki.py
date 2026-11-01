import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/monitoring-remote-pki.py"
SPEC = importlib.util.spec_from_file_location("monitoring_remote_pki", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RemotePkiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = tempfile.TemporaryDirectory()
        MODULE.generate(Path(cls.original.name))

    @classmethod
    def tearDownClass(cls):
        cls.original.cleanup()

    def test_rejects_client_private_key_from_server_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "pki"
            shutil.copytree(self.original.name, copy)
            shutil.copyfile(copy / "server.key", copy / "client.key")
            with self.assertRaisesRegex(RuntimeError, "client certificate does not match"):
                MODULE.validate(copy)

    def test_rejects_inconsistent_cluster_trust_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "pki"
            shutil.copytree(self.original.name, copy)
            (copy / "client-ca.crt").write_text("different trust anchor")
            with self.assertRaisesRegex(RuntimeError, "CA certificates differ"):
                MODULE.validate(copy)


if __name__ == "__main__":
    unittest.main()
