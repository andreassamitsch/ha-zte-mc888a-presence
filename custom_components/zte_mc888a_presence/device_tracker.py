"""Native device trackers for explicitly selected client MAC addresses."""
from __future__ import annotations

from datetime import timezone

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TRACKED_DEVICES, DOMAIN, parse_tracked_devices
from .coordinator import ZTECoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create trackers only for explicitly configured devices."""
    coordinator: ZTECoordinator = entry.runtime_data
    tracked = parse_tracked_devices(entry.options.get(CONF_TRACKED_DEVICES, ""))
    async_add_entities(
        ZTEPresenceTracker(coordinator, mac, name)
        for mac, name in tracked.items()
    )


class ZTEPresenceTracker(CoordinatorEntity[ZTECoordinator], ScannerEntity):
    """A phone or other client detected by the router."""

    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZTECoordinator, mac: str, name: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_mac_address = mac
        # In HA 2026.11, ScannerEntity uses the device's name. No entity name.
        self._attr_name = None
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            name=name,
        )

    @property
    def is_connected(self) -> bool:
        """Keep home for a grace period after the last successful sighting."""
        return self.coordinator.is_present(self._mac)

    @property
    def ip_address(self) -> str | None:
        device = (self.coordinator.data or {}).get(self._mac)
        return device.ip if device else None

    @property
    def hostname(self) -> str | None:
        device = (self.coordinator.data or {}).get(self._mac)
        return device.hostname if device else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Expose useful local diagnostics; no router credentials."""
        last_seen = self.coordinator.last_seen.get(self._mac)
        return {
            "last_seen": last_seen.isoformat() if last_seen else None,
        }
