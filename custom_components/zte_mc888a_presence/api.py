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
from time import monotonic
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
    if value is None:
        raise ZTEProtocolError("Missing device-list response")
    if value == "":
        # An expired login often returns an empty string instead of an array.
        # A real zero-client response must be represented by [].
        raise ZTEProtocolError("Router returned an empty device-list field")
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
        self._last_reauth_attempt: float | None = None
        self._reauth_cooldown_seconds = 300

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

    async def _get_verified_clients(self) -> dict[str, ZTEClientDevice]:
        """Read both lists, rejecting invalid or implausible Wi-Fi responses.

        On the supported MC888A home network, Wi-Fi is never genuinely empty.
        A blank or empty station_list is therefore not evidence of absence.
        Never trust wifi_access_sta_num == 0 as confirmation: it can also
        return zero when the router session has silently expired.
        """
        wifi = await self._read_device_list("station_list", "wifi")
        if not wifi:
            raise ZTEProtocolError(
                "Router returned 0 Wi-Fi clients; treating scan as invalid"
            )

        lan = await self._read_device_list("lan_station_list", "ethernet")
        # A missing LAN device is legitimate; zero Wi-Fi clients is not.
        return {client.mac: client for client in [*lan, *wifi]}

    async def async_get_clients(self) -> dict[str, ZTEClientDevice]:
        """Read clients; renew an invalid session once with a cooldown.

        False absence is more dangerous than an unavailable tracker for
        heating/presence automations. A failed scan must never become {}.
        """
        async with self._lock:
            if not self._authenticated:
                await self._login()
            try:
                return await self._get_verified_clients()
            except ZTEProtocolError as exc:
                now = monotonic()
                if (
                    self._last_reauth_attempt is not None
                    and now - self._last_reauth_attempt < self._reauth_cooldown_seconds
                ):
                    # Avoid repeated admin logins every minute if the router
                    # remains unresponsive or stops returning its client list.
                    raise ZTEProtocolError(
                        "Invalid router client list; re-login on cooldown"
                    ) from exc

                self._last_reauth_attempt = now
                _LOGGER.warning(
                    "ZTE device list invalid or empty; renewing HTTPS session once"
                )
                # A fresh cookie jar is essential. Merely issuing LOGIN on an
                # expired HTTP session may silently return blank lists again.
                await self.async_close()
                await self._login()

                # If the new authenticated session still reports zero clients,
                # propagate an error to Home Assistant's coordinator.
                return await self._get_verified_clients()
