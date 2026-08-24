"""Sensor entities for the Azure Standard integration."""
from __future__ import annotations

import logging
from datetime import date

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AzureStandardCoordinator
from .entity import AzureStandardEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azure Standard sensor entities from a config entry."""
    coordinator: AzureStandardCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Register callback for live product sensor creation (used in later phases)
    from homeassistant.const import Platform
    coordinator.register_platform_callback(Platform.SENSOR, async_add_entities)

    # Static drop/cutoff sensors — always available (no auth required)
    entities: list[AzureStandardEntity] = [
        NextCutoffSensor(coordinator),
        DaysUntilCutoffSensor(coordinator),
        DropNameSensor(coordinator),
        DeliveryDateSensor(coordinator),
    ]

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Drop & Cutoff sensors (public, no auth)
# ---------------------------------------------------------------------------


class NextCutoffSensor(AzureStandardEntity, SensorEntity):
    """Date of the next order cutoff for this drop."""

    _attr_unique_id_suffix = "next_cutoff"
    _attr_translation_key = "next_cutoff"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_next_cutoff"

    @property
    def native_value(self) -> date | None:
        """Return the next cutoff date."""
        return self.coordinator.data.next_cutoff if self.coordinator.data else None


class DaysUntilCutoffSensor(AzureStandardEntity, SensorEntity):
    """Integer countdown of days until the next order cutoff."""

    _attr_translation_key = "days_until_cutoff"
    _attr_native_unit_of_measurement = "days"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_days_until_cutoff"

    @property
    def native_value(self) -> int | None:
        """Return the number of days until the cutoff, or None if unknown."""
        if not self.coordinator.data:
            return None
        cutoff = self.coordinator.data.next_cutoff
        if cutoff is None:
            return None
        return (cutoff - date.today()).days


class DropNameSensor(AzureStandardEntity, SensorEntity):
    """Name of the user's assigned drop location."""

    _attr_translation_key = "drop_name"
    _attr_icon = "mdi:map-marker"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_drop_name"

    @property
    def native_value(self) -> str | None:
        """Return the drop name."""
        if not self.coordinator.data or not self.coordinator.data.drop:
            return None
        return self.coordinator.data.drop.get("name")

    @property
    def extra_state_attributes(self) -> dict:
        """Return drop ID and geographic info as extra attributes."""
        if not self.coordinator.data or not self.coordinator.data.drop:
            return {}
        drop = self.coordinator.data.drop
        return {
            "drop_id": drop.get("id"),
            "geo": drop.get("geo"),
        }


class DeliveryDateSensor(AzureStandardEntity, SensorEntity):
    """Expected pickup / delivery date for the next order."""

    _attr_translation_key = "delivery_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:truck-delivery"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_delivery_date"

    @property
    def native_value(self) -> date | None:
        """Return the next delivery date."""
        return self.coordinator.data.delivery_date if self.coordinator.data else None
