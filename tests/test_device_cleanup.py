"""Tests for cleanup decisions; no Home Assistant server required."""
import importlib.util
from pathlib import Path
import unittest

file = (
    Path(__file__).parents[1]
    / "custom_components"
    / "zte_mc888a_presence"
    / "const.py"
)
spec = importlib.util.spec_from_file_location("zte_cleanup_const", file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

MAC_TYPE = "mac"
S23 = "02:11:22:33:44:55"
OLD_PHONE = "3E:C4:B1:D3:AE:33"


class RetiredDeviceTests(unittest.TestCase):
    def test_retired_phone_removed_after_mac_deleted_from_options(self):
        self.assertTrue(
            module.is_retired_mac_device(
                frozenset({(MAC_TYPE, OLD_PHONE)}), {S23}, MAC_TYPE
            )
        )

    def test_configured_phone_never_removed(self):
        self.assertFalse(
            module.is_retired_mac_device(
                frozenset({(MAC_TYPE, S23)}), {S23}, MAC_TYPE
            )
        )

    def test_router_hub_without_mac_never_removed(self):
        self.assertFalse(
            module.is_retired_mac_device(frozenset(), {S23}, MAC_TYPE)
        )

    def test_other_connection_type_does_not_trigger_removal(self):
        self.assertFalse(
            module.is_retired_mac_device(
                frozenset({("bluetooth", OLD_PHONE)}), {S23}, MAC_TYPE
            )
        )

    def test_mixed_mac_connections_keep_if_any_still_configured(self):
        self.assertFalse(
            module.is_retired_mac_device(
                frozenset({(MAC_TYPE, OLD_PHONE), (MAC_TYPE, S23)}),
                {S23},
                MAC_TYPE,
            )
        )

    def test_lowercase_mac_matches_tracked_mac(self):
        self.assertFalse(
            module.is_retired_mac_device(
                frozenset({(MAC_TYPE, S23.lower())}), {S23}, MAC_TYPE
            )
        )

    def test_invalid_mac_does_not_delete(self):
        self.assertFalse(
            module.is_retired_mac_device(
                frozenset({(MAC_TYPE, "unknown")}), {S23}, MAC_TYPE
            )
        )


if __name__ == "__main__":
    unittest.main()
