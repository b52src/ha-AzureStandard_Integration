"""Binary sensor entities for the Azure Standard integration."""
from __future__ import annotations

import logging
from datetime import date

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
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
    """Set up Azure Standard binary sensor entities from a config entry."""
    from .const import MODE_ACCOUNT

    coordinator: AzureStandardCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Register callback for live product binary sensor creation (later phases)
    from homeassistant.const import Platform
    coordinator.register_platform_callback(Platform.BINARY_SENSOR, async_add_entities)

    entities: list = [OrderWindowOpenBinarySensor(coordinator)]
    if entry.data.get("mode") == MODE_ACCOUNT:
        entities.append(OrderPlacedBinarySensor(coordinator))

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Drop & Cutoff binary sensors (public, no auth)
# ---------------------------------------------------------------------------


class OrderWindowOpenBinarySensor(AzureStandardEntity, BinarySensorEntity):
    """ON when the order window is open (i.e., today is before the cutoff).

    Use this in automations to gate order-related notifications — e.g., only
    send a shopping-list reminder when the order window is still open.
    """

    _attr_translation_key = "order_window_open"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:cart-check"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_order_window_open"

    @property
    def is_on(self) -> bool | None:
        """Return True if today is before the next cutoff date."""
        if not self.coordinator.data:
            return None
        cutoff = self.coordinator.data.next_cutoff
        if cutoff is None:
            return None
        return date.today() < cutoff

    @property
    def extra_state_attributes(self) -> dict:
        """Return the next cutoff date as an attribute for easy dashboard use."""
        if not self.coordinator.data:
            return {}
        cutoff = self.coordinator.data.next_cutoff
        return {"next_cutoff": cutoff.isoformat() if cutoff else None}


# ---------------------------------------------------------------------------
# Order binary sensors (account mode only)
# ---------------------------------------------------------------------------


class OrderPlacedBinarySensor(AzureStandardEntity, BinarySensorEntity):
    """ON when the current active order has been placed (checked out).

    While building your cart the order exists as "open" but is not yet
    submitted.  This sensor flips ON once you click Checkout, allowing
    automations to notify you that the order is confirmed.
    """

    _attr_translation_key = "order_placed"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:cart-check"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_order_placed"

    @property
    def is_on(self) -> bool | None:
        """Return True once the active order has been submitted/placed."""
        if not self.coordinator.data:
            return None
        if self.coordinator.data.active_order is None:
            return False
        placed = self.coordinator.data.order_is_placed
        if placed is None:
            return None
        return placed

    @property
    def extra_state_attributes(self) -> dict:
        """Return full cart metadata for dashboard convenience."""
        if not self.coordinator.data or self.coordinator.data.active_order is None:
            return {}
        d = self.coordinator.data
        return {
            "order_id": d.cart_order_id,
            "item_count": d.cart_item_count,
            "total": d.cart_total,
            "cutoff": d.cart_cutoff,
            "delivery": d.cart_delivery,
        }
