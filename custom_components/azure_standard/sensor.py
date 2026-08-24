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
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_ACCOUNT
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
    coordinator.register_platform_callback(Platform.SENSOR, async_add_entities)

    # Static drop/cutoff sensors — always available (no auth required)
    entities: list[AzureStandardEntity] = [
        NextCutoffSensor(coordinator),
        DaysUntilCutoffSensor(coordinator),
        DropNameSensor(coordinator),
        DeliveryDateSensor(coordinator),
    ]

    # Order sensors — account mode only
    if entry.data.get("mode") == MODE_ACCOUNT:
        entities.extend(
            [
                ActiveOrderStatusSensor(coordinator),
                ActiveOrderItemCountSensor(coordinator),
                ActiveOrderTotalSensor(coordinator),
                LastOrderDateSensor(coordinator),
            ]
        )

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


# ---------------------------------------------------------------------------
# Order sensors (account mode only)
# ---------------------------------------------------------------------------


class ActiveOrderStatusSensor(AzureStandardEntity, SensorEntity):
    """Status of the current open order (open / submitted / shipped / delivered)."""

    _attr_translation_key = "active_order_status"
    _attr_icon = "mdi:package-variant-closed"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_active_order_status"

    @property
    def native_value(self) -> str | None:
        """Return the status string of the active order, or None if no open order."""
        if not self.coordinator.data:
            return None
        order = self.coordinator.data.active_order
        if order is None:
            return None
        return str(order.get("status") or order.get("orderStatus") or "").lower() or None

    @property
    def extra_state_attributes(self) -> dict:
        """Return order ID and cutoff date as extra attributes."""
        if not self.coordinator.data or not self.coordinator.data.active_order:
            return {}
        order = self.coordinator.data.active_order
        return {
            "order_id": order.get("id") or order.get("orderId"),
            "cutoff_date": order.get("cutoffDate") or order.get("cutoff-date"),
            "delivery_date": order.get("deliveryDate") or order.get("trip-delivery"),
        }


class ActiveOrderItemCountSensor(AzureStandardEntity, SensorEntity):
    """Number of line items in the current open order."""

    _attr_translation_key = "active_order_item_count"
    _attr_native_unit_of_measurement = "items"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cart"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_active_order_item_count"

    @property
    def native_value(self) -> int | None:
        """Return the line-item count of the active order."""
        if not self.coordinator.data:
            return None
        order = self.coordinator.data.active_order
        if order is None:
            return None
        # The API may expose items as a list under several key names
        items = (
            order.get("items")
            or order.get("orderItems")
            or order.get("line-items")
            or []
        )
        if isinstance(items, list):
            return len(items)
        # Some API responses surface a pre-computed count
        count = order.get("itemCount") or order.get("item-count")
        if count is not None:
            try:
                return int(count)
            except (TypeError, ValueError):
                pass
        return None


class ActiveOrderTotalSensor(AzureStandardEntity, SensorEntity):
    """Dollar total of the current open order."""

    _attr_translation_key = "active_order_total"
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:currency-usd"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_active_order_total"

    @property
    def native_value(self) -> float | None:
        """Return the order total, or None if no active order."""
        if not self.coordinator.data:
            return None
        order = self.coordinator.data.active_order
        if order is None:
            return None
        raw = (
            order.get("total")
            or order.get("orderTotal")
            or order.get("order-total")
        )
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
        return None


class LastOrderDateSensor(AzureStandardEntity, SensorEntity):
    """Date of the most recently completed order."""

    _attr_translation_key = "last_order_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:history"

    def __init__(self, coordinator: AzureStandardCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_last_order_date"

    @property
    def native_value(self) -> date | None:
        """Return the cutoff date of the most recently completed order."""
        if not self.coordinator.data:
            return None
        # Find the most recent delivered/completed order by cutoff date
        terminal = {"delivered", "completed"}
        completed = [
            o
            for o in self.coordinator.data.orders
            if str(o.get("status", "")).lower() in terminal
        ]
        if not completed:
            return None
        latest = max(
            completed,
            key=lambda o: o.get("cutoffDate") or o.get("cutoff-date") or "",
        )
        raw = latest.get("cutoffDate") or latest.get("cutoff-date")
        if not raw:
            return None
        try:
            return date.fromisoformat(str(raw)[:10])
        except (ValueError, TypeError):
            return None
