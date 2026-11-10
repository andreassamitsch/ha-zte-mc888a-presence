"""Local parsing tests that do not require Home Assistant installed."""
import importlib.util
from pathlib import Path
import unittest

file = Path(__file__).parents[1] / "custom_components" / "zte_mc888a_presence" / "const.py"
spec = importlib.util.spec_from_file_location("zte_test_const", file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ConfigParserTest(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(module.normalize_mac("a4-57-a0-3b-b8-8e"), "A4:57:A0:3B:B8:8E")

    def test_named_devices(self):
        result = module.parse_tracked_devices(
            "a4:57:a0:3b:b8:8e=Andi S23, 01:02:03:04:05:06=Iris iPhone"
        )
        self.assertEqual(result["A4:57:A0:3B:B8:8E"], "Andi S23")
        self.assertEqual(len(result), 2)

    def test_invalid_mac(self):
        with self.assertRaises(ValueError):
            module.parse_tracked_devices("Samsung")
    
    def test_safe_host(self):
        self.assertEqual(module.safe_host("192.168.1.1"), "192.168.1.1")
        with self.assertRaises(ValueError):
            module.safe_host("https://192.168.1.1/command")


if __name__ == "__main__":
    unittest.main()
