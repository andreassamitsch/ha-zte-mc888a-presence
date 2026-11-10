"""Shared periodic router polling and presence hysteresis."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZTEError, ZTERouterClient, ZTEClientDevice
from .const import DEFAULT_POLL_SECONDS, DOMAIN


class ZTECoordinator(DataUpdateCoordinator[dict[str, ZTEClientDevice]]):
    """One poll for all sensor and device tracker entities."""

    def __init__(self, hass: HomeAssistant, client: ZTERouterClient, away_seconds: int) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_SECONDS),
        )
        self.client = client
        self.away_seconds = away_seconds
        self.last_seen: dict[str, datetime] = {}
        self.last_success: datetime | None = None

    async def _async_update_data(self) -> dict[str, ZTEClientDevice]:
        try:
            devices = await self.client.async_get_clients()
        except ZTEError as exc:
            # CoordinatorEntity becomes unavailable, never absent, on failure.
            raise UpdateFailed("Router device list unavailable") from exc

        now = datetime.now(timezone.utc)
        for mac in devices:
            self.last_seen[mac] = now
        self.last_success = now
        return devices

    def is_present(self, mac: str) -> bool:
        """Ignore temporary Wi-Fi disconnections for a configurable duration."""
        if self.data and mac in self.data:
            return True
        last_seen = self.last_seen.get(mac)
        return (
            last_seen is not None
            and datetime.now(timezone.utc) - last_seen
            < timedelta(seconds=self.away_seconds)
        )
