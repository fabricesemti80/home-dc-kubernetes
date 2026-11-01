import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "kubernetes/apps/infra-cluster/monitoring/pve-exporter/config/hardware_exporter.py"
SPEC = importlib.util.spec_from_file_location("pve_hardware_exporter", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TemperatureTests(unittest.TestCase):
    def test_nvme_composite_temperature_ignores_time_counters(self):
        smart = {"type": "text", "text": "Temperature:                        30 Celsius\nWarning  Comp. Temperature Time: 0\n"}
        self.assertEqual(MODULE.temperature(smart), 30)

    def test_ata_uses_raw_temperature_not_normalized_attribute(self):
        smart = {"type": "ata", "attributes": [{"id": "194", "name": "Temperature_Celsius", "value": 157, "raw": "38 (Min/Max 13/44)"}]}
        self.assertEqual(MODULE.temperature(smart), 38)

    def test_missing_or_invalid_temperature_is_not_fabricated(self):
        self.assertIsNone(MODULE.temperature({"type": "text", "text": "Temperature: unavailable"}))
        self.assertIsNone(MODULE.temperature({"type": "ata", "attributes": [{"id": "194", "name": "Temperature_Celsius", "raw": "unknown"}]}))


if __name__ == "__main__":
    unittest.main()
