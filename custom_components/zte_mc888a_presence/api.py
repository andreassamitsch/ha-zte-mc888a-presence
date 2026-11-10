"""Local HTTPS API for ZTE MC888A Ultra / ZTE Goform routers.

Only read-only GET calls and the explicit LOGIN action are performed.
Credentials are used solely inside Home Assistant, not logged.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import logging
from typing import Any

import aiohttp

from .const import normalize_mac

_LOGGER = logging.getLogger(__name__)


class ZTEError(Exception):
    """Base error for router communication."""


class ZTEConnectionError(ZTEError):
    """The router did not respond."""


class ZTEAuthError(ZTEError):
    """The router rejected credentials."""


class ZTEProtocolError(ZTEError):
    """The router returned an unsupported or invalid response."""


@dataclass(frozen=True, slots=True)
class ZTEClientDevice:
    """One connected network client."""

    mac: str
    ip: str | None
    hostname: str | None
    connection: str


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _decode_list(value: Any) -> list[dict[str, Any]]:
    """ZTE firmware returns either JSON arrays or JSON-encoded strings."""
    if value == "" or value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise ZTEProtocolError("Unexpected device-list response") from exc
    if not isinstance(value, list) or not all(isinstance(i, dict) for i in value):
        raise ZTEProtocolError("Unexpected device-list format")
    return value


class ZTERouterClient:
    """One authenticated session. No periodic logouts or forced relogins."""

    def __init__(self, host: str, password: str) -> None:
        self.host = host
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self._authenticated = False
        self._lock = asyncio.Lock()

    async def async_close(self) -> None:
        """Close the private router session and discard its cookies."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
        self._authenticated = False

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # The router uses a local, often self-signed certificate.
            # Cookies from a numeric LAN IP require unsafe=True.
            self._session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True),
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=12),
                headers={
                    "Referer": f"https://{self.host}/index.html",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
        return self._session

    async def _request(
        self, *, command: str | None = None, form: dict[str, str] | None = None
    ) -> dict[str, Any]:
        session = self._get_session()
        path = (
            "/goform/goform_set_cmd_process"
            if form is not None else "/goform/goform_get_cmd_process"
        )
        try:
            if form is not None:
                async with session.post(
                    f"https://{self.host}{path}", data=form
                ) as response:
                    response.raise_for_status()
                    content = await response.text()
            else:
                async with session.get(
                    f"https://{self.host}{path}",
                    params={"isTest": "false", "cmd": command or ""},
                ) as response:
                    response.raise_for_status()
                    content = await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            raise ZTEConnectionError("Router HTTPS request failed") from exc

        try:
            parsed = json.loads(content)
        except (TypeError, ValueError) as exc:
            raise ZTEProtocolError("Router did not return JSON") from exc
        if not isinstance(parsed, dict):
            raise ZTEProtocolError("Router returned a non-object response")
        return parsed

    async def _login(self) -> None:
        challenge = await self._request(command="LD")
        ld = challenge.get("LD")
        if not isinstance(ld, str) or not ld:
            raise ZTEProtocolError("Missing router LD challenge")

        # Verified on BD_ATMC888AULTRAV1.0.0B20: no user, LOGIN not
        # LOGIN_MULTI_USER; password = SHA256(SHA256(password) + LD).
        password_hash = _sha256(_sha256(self._password) + ld)
        result = await self._request(
            form={
                "isTest": "false",
                "goformId": "LOGIN",
                "password": password_hash,
            }
        )
        if str(result.get("result")) != "0":
            raise ZTEAuthError("Router rejected the login")
        self._authenticated = True

    async def _read_device_list(self, cmd: str, network: str) -> list[ZTEClientDevice]:
        payload = await self._request(command=cmd)
        if cmd not in payload:
            raise ZTEProtocolError(f"Missing {cmd} response")
        clients = []
        for device in _decode_list(payload[cmd]):
            try:
                mac = normalize_mac(str(device.get("mac_addr", "")))
            except ValueError:
                continue
            hostname = str(device.get("hostname") or "").strip()
            ip = str(device.get("ip_addr") or "").strip()
            clients.append(
                ZTEClientDevice(
                    mac=mac,
                    ip=ip or None,
                    hostname=hostname if hostname not in ("", "--") else None,
                    connection=network,
                )
            )
        return clients

    async def async_get_clients(self) -> dict[str, ZTEClientDevice]:
        """Get all currently connected clients; reuse the login session.

        A zero-length station list despite a nonzero Wi-Fi count suggests
        a lost login session. Attempt one reauthentication, then fail closed
        rather than marking everybody away.
        """
        async with self._lock:
            if not self._authenticated:
                await self._login()

            wifi = await self._read_device_list("station_list", "wifi")
            lan = await self._read_device_list("lan_station_list", "ethernet")

            if not wifi:
                count_payload = await self._request(command="wifi_access_sta_num")
                try:
                    wifi_count = int(count_payload.get("wifi_access_sta_num", 0))
                except (ValueError, TypeError):
                    wifi_count = 0
                if wifi_count > 0:
                    self._authenticated = False
                    await self._login()
                    wifi = await self._read_device_list("station_list", "wifi")
                    lan = await self._read_device_list("lan_station_list", "ethernet")
                    if not wifi:
                        raise ZTEProtocolError(
                            "Wi-Fi clients are present but station_list is empty"
                        )

            # One router-wide request per platform, not per tracked device.
            return {client.mac: client for client in [*lan, *wifi]}
