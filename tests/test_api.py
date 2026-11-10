"""Regression tests: reject zero Wi-Fi snapshots and avoid false absence.

No Home Assistant instance, router, or credentials are needed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1] / "custom_components" / "zte_mc888a_presence"

# Import api.py without importing integration __init__ (needs Home Assistant).
for pkg in ("custom_components", "custom_components.zte_mc888a_presence"):
    package = types.ModuleType(pkg)
    package.__path__ = [str(ROOT if pkg.endswith("zte_mc888a_presence") else ROOT.parent)]
    sys.modules.setdefault(pkg, package)

for name in ("const", "api"):
    full = "custom_components.zte_mc888a_presence." + name
    spec = importlib.util.spec_from_file_location(full, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)

api = sys.modules["custom_components.zte_mc888a_presence.api"]
DEVICE = api.ZTEClientDevice(
    mac="AA:BB:CC:DD:EE:FF", ip="192.168.1.20", hostname="Phone",
    connection="wifi",
)


class FakeRouter(api.ZTERouterClient):
    """Simulate changing router API responses without network I/O."""

    def __init__(self, wifi_scans):
        super().__init__("192.168.1.1", "unused")
        self._wifi_scans = list(wifi_scans)
        self.logins = 0
        self.wifi_reads = 0

    async def _login(self):
        self.logins += 1
        self._authenticated = True

    async def _read_device_list(self, cmd, network):
        if network == "ethernet":
            return []
        self.wifi_reads += 1
        if not self._wifi_scans:
            raise AssertionError("unexpected extra router poll")
        value = self._wifi_scans.pop(0)
        if value == "blank":
            raise api.ZTEProtocolError("Empty station list")
        return value


class RouterSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_scan_does_not_relogin(self):
        router = FakeRouter([[DEVICE], [DEVICE]])
        self.assertEqual(len(await router.async_get_clients()), 1)
        self.assertEqual(len(await router.async_get_clients()), 1)
        self.assertEqual(router.logins, 1)

    async def test_zero_wifi_snapshot_forces_fresh_login(self):
        router = FakeRouter([[], [DEVICE]])
        result = await router.async_get_clients()
        self.assertIn(DEVICE.mac, result)
        self.assertEqual(router.logins, 2)

    async def test_zero_after_relogin_is_an_error_not_empty_result(self):
        router = FakeRouter([[], []])
        with self.assertRaises(api.ZTEProtocolError):
            await router.async_get_clients()
        self.assertEqual(router.logins, 2)

    async def test_relogin_cooldown_avoids_router_login_storm(self):
        router = FakeRouter([[], [], []])
        with self.assertRaises(api.ZTEProtocolError):
            await router.async_get_clients()
        with self.assertRaises(api.ZTEProtocolError):
            await router.async_get_clients()
        self.assertEqual(router.logins, 2)
        self.assertEqual(router.wifi_reads, 3)

    async def test_good_scan_followed_by_empty_is_not_success(self):
        router = FakeRouter([[DEVICE], [], []])
        self.assertIn(DEVICE.mac, await router.async_get_clients())
        with self.assertRaises(api.ZTEProtocolError):
            await router.async_get_clients()


class RouterPayloadTests(unittest.TestCase):
    def test_expired_session_blank_field_rejected(self):
        with self.assertRaises(api.ZTEProtocolError):
            api._decode_list("")

    def test_non_json_field_rejected(self):
        with self.assertRaises(api.ZTEProtocolError):
            api._decode_list("not-json")

    def test_normal_json_list_still_supported(self):
        self.assertEqual(api._decode_list("[]"), [])
        self.assertEqual(api._decode_list([]), [])


if __name__ == "__main__":
    unittest.main()
