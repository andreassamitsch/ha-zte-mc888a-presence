"""Constants and helpers for ZTE MC888A Presence."""
from __future__ import annotations

import re
from collections.abc import Mapping

DOMAIN = "zte_mc888a_presence"
PLATFORMS = ["device_tracker", "sensor"]
DEFAULT_HOST = "192.168.1.1"
DEFAULT_POLL_SECONDS = 60
DEFAULT_AWAY_SECONDS = 300

CONF_TRACKED_DEVICES = "tracked_devices"
CONF_AWAY_SECONDS = "away_seconds"

MAC_PATTERN = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")


def normalize_mac(value: str) -> str:
    """Normalize a colon- or dash-separated hardware address."""
    mac = value.strip().upper().replace("-", ":")
    if not MAC_PATTERN.fullmatch(mac):
        raise ValueError("Invalid MAC address")
    return mac


def parse_tracked_devices(value: str) -> dict[str, str]:
    """Read comma/newline/semicolon separated MAC[=friendly name] entries."""
    result: dict[str, str] = {}
    for item in re.split(r"[,;\n]+", value):
        item = item.strip()
        if not item:
            continue
        mac_text, sep, friendly_name = item.partition("=")
        mac = normalize_mac(mac_text)
        result[mac] = friendly_name.strip() if sep and friendly_name.strip() else mac
    if len(result) > 100:
        raise ValueError("Too many tracked devices")
    return result


def safe_host(host: str) -> str:
    """Accept an IPv4 address or DNS name; never accept a URL/path."""
    host = host.strip().lower()
    if not host or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,252}", host):
        raise ValueError("Invalid router host")
    if ".." in host or host.endswith("."):
        raise ValueError("Invalid router host")
    return host
