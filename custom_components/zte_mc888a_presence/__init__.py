"""ZTE MC888A Ultra presence integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .api import ZTERouterClient
from .const import (
    CONF_AWAY_SECONDS,
    CONF_TRACKED_DEVICES,
    DEFAULT_AWAY_SECONDS,
    DOMAIN,
    PLATFORMS,
    is_retired_mac_device,
    parse_tracked_devices,
)
from .coordinator import ZTECoordinator


@callback
def _is_retired_tracker_device(entry: ConfigEntry, device: DeviceEntry) -> bool:
    """Only allow removal of our own MAC device after it is unconfigured.

    The router hub is deliberately protected: it has a DOMAIN identifier
    and no tracked MAC. A tracked person's phone is also protected until
    its MAC is removed from the integration's options.
    """
    if device.config_entry_id != entry.entry_id:
        return False

    if any(domain == DOMAIN for domain, _ in device.identifiers):
        return False

    tracked = set(
        parse_tracked_devices(entry.options.get(CONF_TRACKED_DEVICES, ""))
    )
    return is_retired_mac_device(
        device.connections, tracked, dr.CONNECTION_NETWORK_MAC
    )


@callback
def _cleanup_retired_tracker_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove retired phone devices and their entity-registry entries.

    This runs after every configuration reload. DeviceRegistry removes the
    child's entity registry entries when its device is removed. It does not
    remove the active MACs or the router hub.
    """
    registry = dr.async_get(hass)
    for device in list(dr.async_entries_for_config_entry(registry, entry.entry_id)):
        if _is_retired_tracker_device(entry, device):
            registry.async_remove_device(device.id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Enable Home Assistant's Delete button for retired client devices."""
    return _is_retired_tracker_device(entry, device_entry)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the router and its tracked devices."""
    client = ZTERouterClient(entry.data["host"], entry.data["password"])
    coordinator = ZTECoordinator(
        hass, client, int(entry.options.get(CONF_AWAY_SECONDS, DEFAULT_AWAY_SECONDS))
    )

    try:
        await coordinator.async_config_entry_first_refresh()
        _cleanup_retired_tracker_devices(hass, entry)
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
