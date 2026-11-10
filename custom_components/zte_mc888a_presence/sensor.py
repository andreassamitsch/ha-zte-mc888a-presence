"""Router client count and last good update sensors."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZTECoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create three client-count sensors and one timestamp sensor."""
    coordinator = entry.runtime_data
    async_add_entities(
        ZTERouterSensor(coordinator, entry, kind)
        for kind in ("wifi", "ethernet", "total", "last_success")
    )


class ZTERouterSensor(CoordinatorEntity[ZTECoordinator], SensorEntity):
    """A router-wide diagnostic sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ZTECoordinator, entry: ConfigEntry, kind: str):
        super().__init__(coordinator)
        self.kind = kind
        self._attr_unique_id = f"{entry.entry_id}_{kind}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="ZTE MC888A Ultra",
            manufacturer="ZTE",
            model="MC888A Ultra",
            configuration_url=f"https://{entry.data['host']}/index.html",
        )
        self._attr_translation_key = kind
        if kind == "last_success":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        else:
            self._attr_native_unit_of_measurement = "devices"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | datetime | None:
        if self.kind == "last_success":
            return self.coordinator.last_success
        data = self.coordinator.data or {}
        if self.kind == "total":
            return len(data)
        return sum(1 for item in data.values() if item.connection == self.kind)
