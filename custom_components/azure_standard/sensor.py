"""Sensor entities for the Azure Standard integration."""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .discovery import ProductStats

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_ACCOUNT, CONF_TRACKED_PRODUCTS
from .coordinator import AzureStandardCoordinator
from .entity import AzureStandardEntity

_LOGGER = logging.getLogger(__name__)


def _list_slug(lst: dict) -> str:
    """Return a stable slug for a shopping list dict.

    Prefers the ``name`` field, cleaned to lowercase snake_case, so the sensor
    entity ID is human-readable (e.g. ``sensor.azure_standard_list_staples_count``).
    Falls back to the list's numeric/string id if the name is absent.
    """
    name = lst.get("name") or lst.get("listName") or lst.get("title") or ""
    if name:
        return re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_")
    return str(lst.get("id") or lst.get("uid") or "unknown")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azure Standard sensor entities from a config entry."""
    coordinator: AzureStandardCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Register callback for live sensor creation (shopping lists, product sensors)
    coordinator.register_platform_callback(Platform.SENSOR, async_add_entities)

    # Static drop/cutoff sensors — always available (no auth required)
    entities: list[AzureStandardEntity] = [  # type: ignore[assignment]
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

        # Shopping list sensors — seeded from data already in the coordinator
        # (coordinator polls lists on its own interval; here we only add the
        # sensors for lists that are known at setup time so entities survive
        # an HA restart without waiting for the next coordinator tick).
        if coordinator.data and coordinator.data.product_lists:
            list_entities = [
                ShoppingListSensor(coordinator, lst)
                for lst in coordinator.data.product_lists
            ]
            entities.extend(list_entities)
            # Mark these lists as known so the coordinator's live-creation
            # path does not create duplicates on the next poll.
            coordinator._known_list_ids = {
                str(lst.get("id") or lst.get("uid") or "")
                for lst in coordinator.data.product_lists
            }

        # Product sensors — seeded from tracked products already in options
        tracked = coordinator.entry.options.get(CONF_TRACKED_PRODUCTS, [])
        if tracked and coordinator.data and coordinator.data.product_stats:
            product_entities: list[AzureStandardEntity] = []
            for code in tracked:
                if code in coordinator.data.product_stats:
                    product_entities.extend(_make_product_sensors(coordinator, code))
            if product_entities:
                entities.extend(product_entities)
            coordinator._known_product_codes = set(tracked)

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


# ---------------------------------------------------------------------------
# Shopping list sensors (account mode, dynamically created)
# ---------------------------------------------------------------------------


class ShoppingListSensor(AzureStandardEntity, SensorEntity):
    """Item count for a single Azure Standard saved shopping list.

    One sensor is created per list.  The sensor's state is the total number
    of items in the list; an ``items`` attribute surfaces the full item
    array so dashboards and automations can inspect individual products.

    The unique ID is derived from the list's server-side ID (not its name)
    so that renaming the list in Azure Standard does not break the HA entity.
    """

    _attr_native_unit_of_measurement = "items"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:format-list-bulleted"

    def __init__(
        self, coordinator: AzureStandardCoordinator, list_data: dict
    ) -> None:
        super().__init__(coordinator)
        self._list_id = str(list_data.get("id") or list_data.get("uid") or "")
        self._attr_unique_id = f"{coordinator.entry.entry_id}_list_{self._list_id}"
        # Human-readable name shown in the UI: "Staples list", "Weekly list", …
        slug = _list_slug(list_data)
        self._attr_name = f"{slug.replace('_', ' ').title()} list"

    def _current_list(self) -> dict | None:
        """Return the matching list dict from the latest coordinator data."""
        if not self.coordinator.data:
            return None
        for lst in self.coordinator.data.product_lists:
            if str(lst.get("id") or lst.get("uid") or "") == self._list_id:
                return lst
        return None

    @property
    def native_value(self) -> int | None:
        """Return the number of items in the list."""
        lst = self._current_list()
        if lst is None:
            return None
        items = lst.get("items") or []
        if isinstance(items, list):
            return len(items)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return list metadata and item details as extra attributes.

        Item shape (confirmed from live API):
          {id, productList, quantity, isPinned, pieceMetaId, slug,
           image, name, directReplacement, createdAt, productCode}
        """
        lst = self._current_list()
        if lst is None:
            return {}
        items_raw = lst.get("items") or []
        # Normalise each item to {name, code, qty, slug} for easy automation use
        items: list[dict] = []
        if isinstance(items_raw, list):
            for item in items_raw:
                if isinstance(item, dict):
                    items.append(
                        {
                            "name": item.get("name", ""),
                            "code": item.get("productCode", ""),
                            "qty": item.get("quantity", 1),
                            "slug": item.get("slug", ""),
                            "pinned": item.get("isPinned", False),
                        }
                    )
        return {
            "list_id": self._list_id,
            "list_name": lst.get("name") or "",
            "items": items,
            "last_updated": lst.get("updatedAt") or lst.get("updated_at") or None,
        }


# ---------------------------------------------------------------------------
# Product sensor helpers
# ---------------------------------------------------------------------------

_REORDER_THRESHOLD_DAYS = 30  # default; phase 8 will add per-product config


def _make_product_sensors(
    coordinator: "AzureStandardCoordinator",
    code: str,
) -> list["AzureStandardEntity"]:
    """Return the group of 4 sensors for a single tracked product code."""
    return [
        ProductLastOrderedSensor(coordinator, code),
        ProductTimesOrderedSensor(coordinator, code),
        ProductDaysSinceSensor(coordinator, code),
        ProductReorderDueSensor(coordinator, code),
    ]


# ---------------------------------------------------------------------------
# Per-product sensors (account mode, dynamically created)
# ---------------------------------------------------------------------------


class _ProductSensorBase(AzureStandardEntity, SensorEntity):
    """Shared base for all per-product sensors.

    Subclasses only need to set ``_metric`` (unique_id suffix / translation key)
    and implement ``native_value``.
    """

    _metric: str = ""

    def __init__(self, coordinator: AzureStandardCoordinator, code: str) -> None:
        super().__init__(coordinator)
        self._code = code
        self._attr_unique_id = f"{DOMAIN}_{code.lower()}_{self._metric}"
        self._attr_name = f"{code} {self._metric.replace('_', ' ').title()}"

    def _stats(self) -> "ProductStats | None":
        """Return the ProductStats for this code, or None if unavailable."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.product_stats.get(self._code)


class ProductLastOrderedSensor(_ProductSensorBase):
    """ISO date string of the most recent order for this product."""

    _metric = "last_ordered"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-check"

    @property
    def native_value(self) -> date | None:
        """Return the last-ordered date, or None if unknown."""
        stats = self._stats()
        return stats.last_ordered if stats else None


class ProductTimesOrderedSensor(_ProductSensorBase):
    """Total number of times this product has been ordered."""

    _metric = "times_ordered"
    _attr_native_unit_of_measurement = "orders"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    @property
    def native_value(self) -> int | None:
        """Return the order count, or None if unknown."""
        stats = self._stats()
        return stats.order_count if stats else None


class ProductDaysSinceSensor(_ProductSensorBase):
    """Days elapsed since this product was last ordered."""

    _metric = "days_since"
    _attr_native_unit_of_measurement = "d"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> int | None:
        """Return days since last order, or None if unknown."""
        stats = self._stats()
        return stats.days_since_last_order if stats else None


class ProductReorderDueSensor(_ProductSensorBase):
    """True when days since last order exceeds the reorder threshold."""

    _metric = "reorder_due"
    _attr_icon = "mdi:cart-arrow-down"

    @property
    def native_value(self) -> str | None:
        """Return 'true' / 'false', or None if data is unavailable."""
        stats = self._stats()
        if stats is None or stats.days_since_last_order is None:
            return None
        return "true" if stats.days_since_last_order >= _REORDER_THRESHOLD_DAYS else "false"
