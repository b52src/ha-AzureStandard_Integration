"""Data coordinator for the Azure Standard integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AzureStandardApiClient
from .const import (
    CONF_DROP_ID,
    CONF_MODE,
    DOMAIN,
    MODE_MANUAL,
    SCAN_INTERVAL_PUBLIC,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class AzureStandardData:
    """Snapshot of all data fetched during a coordinator update.

    Fields that require account login are ``None`` in manual mode.
    """

    # ---- Public (no auth needed) ----
    drop: dict | None = None
    next_cutoff: date | None = None
    delivery_date: date | None = None

    # ---- Account (None if mode=manual or not yet fetched) ----
    active_order: dict | None = None
    orders: list[dict] = field(default_factory=list)
    product_lists: list[dict] = field(default_factory=list)
    ordered_products: list[dict] = field(default_factory=list)
    account_credit: float | None = None
    pending_payment: float | None = None

    # ---- Product discovery ----
    product_stats: dict[str, Any] = field(default_factory=dict)  # keyed by packaging_code
    suggested_products: list[Any] = field(default_factory=list)
    tracked_products: list[str] = field(default_factory=list)
    newly_confirmed_products: list[str] = field(default_factory=list)


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date string to a :class:`datetime.date`, or return ``None``."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _find_next_cutoff(drop: dict) -> tuple[date | None, date | None]:
    """Extract the nearest future cutoff and its paired delivery date from a drop dict.

    The Azure Standard API embeds cutoff schedules under
    ``order-frequency[].cutoff`` as ISO date strings. Each schedule entry
    may also carry a ``trip-delivery`` date.

    Returns ``(next_cutoff_date, delivery_date)``.
    """
    today = date.today()
    best_cutoff: date | None = None
    best_delivery: date | None = None

    for freq in drop.get("order-frequency", []):
        raw_cutoff = freq.get("cutoff") or freq.get("cutoffDate") or freq.get("cutoff-date")
        cutoff = _parse_date(raw_cutoff)
        if cutoff is None or cutoff < today:
            continue
        if best_cutoff is None or cutoff < best_cutoff:
            best_cutoff = cutoff
            raw_delivery = (
                freq.get("trip-delivery")
                or freq.get("tripDelivery")
                or freq.get("delivery-date")
                or freq.get("deliveryDate")
            )
            best_delivery = _parse_date(raw_delivery)

    return best_cutoff, best_delivery


class AzureStandardCoordinator(DataUpdateCoordinator[AzureStandardData]):
    """Coordinator that polls the Azure Standard API and distributes data.

    In **manual** mode only the public drop/cutoff data is fetched (no
    credentials required). In **account** mode additional authenticated
    endpoints are polled on their own intervals (handled in later phases).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AzureStandardApiClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL_PUBLIC,
        )
        self.entry = entry
        self.client = client
        # Callbacks registered by each platform to allow live entity creation
        self._platform_callbacks: dict[Platform, Any] = {}

    def register_platform_callback(self, platform: Platform, callback) -> None:
        """Register an *async_add_entities* callback for a platform."""
        self._platform_callbacks[platform] = callback

    async def _async_update_data(self) -> AzureStandardData:
        """Fetch the latest data from the Azure Standard API."""
        drop_id: int = self.entry.data[CONF_DROP_ID]
        mode: str = self.entry.data.get(CONF_MODE, MODE_MANUAL)

        try:
            drop = await self.client.get_drop(drop_id)
        except Exception as err:
            raise UpdateFailed(f"Error fetching drop {drop_id}: {err}") from err

        next_cutoff, delivery_date = _find_next_cutoff(drop)

        return AzureStandardData(
            drop=drop,
            next_cutoff=next_cutoff,
            delivery_date=delivery_date,
        )
