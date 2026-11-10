"""ZTE MC888A Ultra presence integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import ZTERouterClient
from .const import (
    CONF_AWAY_SECONDS,
    CONF_TRACKED_DEVICES,
    DEFAULT_AWAY_SECONDS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import ZTECoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the router and its tracked devices."""
    client = ZTERouterClient(entry.data["host"], entry.data["password"])
    coordinator = ZTECoordinator(
        hass, client, int(entry.options.get(CONF_AWAY_SECONDS, DEFAULT_AWAY_SECONDS))
    )

    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await client.async_close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entities and close the authenticated cookie session."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.client.async_close()
    return True
