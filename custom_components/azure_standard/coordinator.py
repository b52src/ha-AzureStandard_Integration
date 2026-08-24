"""Data coordinator for the Azure Standard integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AzureStandardApiClient
from .const import (
    CONF_DROP_ID,
    CONF_EMAIL,
    CONF_MODE,
    CONF_SESSION_COOKIE,
    DOMAIN,
    MODE_ACCOUNT,
    MODE_MANUAL,
    SCAN_INTERVAL_ORDERS,
    SCAN_INTERVAL_PUBLIC,
    SCAN_INTERVAL_SESSION,
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


# ---------------------------------------------------------------------------
# Date / schedule helpers
# ---------------------------------------------------------------------------


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
        raw_cutoff = (
            freq.get("cutoff")
            or freq.get("cutoffDate")
            or freq.get("cutoff-date")
        )
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


# ---------------------------------------------------------------------------
# Order helpers
# ---------------------------------------------------------------------------


def _find_active_order(orders: list[dict]) -> dict | None:
    """Return the most recent non-delivered order, or None."""
    terminal = {"delivered", "cancelled", "refunded"}
    candidates = [o for o in orders if o.get("status", "").lower() not in terminal]
    if not candidates:
        return None
    # Most recent cutoff date first
    return max(
        candidates,
        key=lambda o: o.get("cutoffDate") or o.get("cutoff-date") or "",
    )


def _extract_credit(account_entries: list[dict]) -> float | None:
    """Return the current account credit balance from the entries list."""
    # The last entry's running balance is the current balance.
    # Fall back to summing credit/debit entries if structure is uncertain.
    if not account_entries:
        return None
    last = account_entries[-1]
    balance = last.get("balance") or last.get("runningBalance")
    if balance is not None:
        try:
            return float(balance)
        except (TypeError, ValueError):
            pass
    return None


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class AzureStandardCoordinator(DataUpdateCoordinator[AzureStandardData]):
    """Coordinator that polls the Azure Standard API and distributes data.

    In **manual** mode only the public drop/cutoff data is fetched (no
    credentials required).

    In **account** mode the coordinator additionally fetches orders and account
    data on their own intervals, managed via internal timestamps rather than
    multiple coordinators. The per-interval logic is intentionally simple:
    on every public-interval tick the coordinator checks whether the longer
    intervals have also elapsed and appends those fetches to the same update.

    **Re-authentication**: On an HTTP 401/403 the coordinator calls
    :meth:`login` once and retries the failing request. If the retry also
    fails, :class:`ConfigEntryAuthFailed` is raised, which triggers HA's
    built-in repair notification asking the user to re-enter credentials.
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

        # Callbacks registered by each platform for live entity creation
        self._platform_callbacks: dict[Platform, Any] = {}

        # Timestamps controlling account-data sub-intervals
        self._last_orders_fetch: datetime | None = None
        self._last_session_check: datetime | None = None

        # Restore the session cookie from entry.data so the client is
        # immediately authenticated without a re-login after HA restart.
        if entry.data.get(CONF_MODE) == MODE_ACCOUNT:
            cookie = entry.data.get(CONF_SESSION_COOKIE, "")
            if cookie:
                self.client.restore_cookie(cookie)

    def register_platform_callback(self, platform: Platform, callback: Any) -> None:
        """Register an *async_add_entities* callback for a platform."""
        self._platform_callbacks[platform] = callback

    # ------------------------------------------------------------------
    # Re-authentication helper
    # ------------------------------------------------------------------

    async def _reauth(self) -> None:
        """Attempt to re-authenticate using stored credentials.

        Raises :class:`ConfigEntryAuthFailed` if re-login is not possible
        (e.g., no stored email — user must reconfigure via the HA UI).
        """
        email = self.entry.data.get(CONF_EMAIL)
        if not email:
            raise ConfigEntryAuthFailed("No stored credentials — please reconfigure.")

        # We can't re-use a stored plaintext password (by design). Raise
        # ConfigEntryAuthFailed so HA prompts the user via the repair UI.
        _LOGGER.warning(
            "Azure Standard session expired for %s — reauthentication required.",
            email,
        )
        raise ConfigEntryAuthFailed(
            f"Session expired for {email}. Please reconfigure the integration."
        )

    async def _authenticated_get(self, coro_factory) -> Any:
        """Execute *coro_factory()* and retry once after re-auth on 401/403.

        :param coro_factory: Zero-argument callable that returns a coroutine.
        """
        try:
            return await coro_factory()
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                await self._reauth()
            raise

    # ------------------------------------------------------------------
    # Sub-interval predicates
    # ------------------------------------------------------------------

    def _orders_due(self) -> bool:
        if self._last_orders_fetch is None:
            return True
        return datetime.now() - self._last_orders_fetch >= SCAN_INTERVAL_ORDERS

    def _session_check_due(self) -> bool:
        if self._last_session_check is None:
            return True
        return datetime.now() - self._last_session_check >= SCAN_INTERVAL_SESSION

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> AzureStandardData:
        """Fetch the latest data from the Azure Standard API."""
        drop_id: int = self.entry.data[CONF_DROP_ID]
        mode: str = self.entry.data.get(CONF_MODE, MODE_MANUAL)

        # ---- Public data (always fetched) ----
        try:
            drop = await self.client.get_drop(drop_id)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching drop {drop_id}: {err}") from err

        next_cutoff, delivery_date = _find_next_cutoff(drop)

        result = AzureStandardData(
            drop=drop,
            next_cutoff=next_cutoff,
            delivery_date=delivery_date,
        )

        if mode != MODE_ACCOUNT:
            return result

        # ---- Session health check (every SCAN_INTERVAL_SESSION) ----
        if self._session_check_due():
            self._last_session_check = datetime.now()
            try:
                valid = await self.client.validate_session()
            except aiohttp.ClientError:
                valid = False
            if not valid:
                await self._reauth()

        # ---- Account data: orders (every SCAN_INTERVAL_ORDERS) ----
        if self._orders_due():
            self._last_orders_fetch = datetime.now()
            try:
                orders = await self._authenticated_get(self.client.get_orders)
            except (aiohttp.ClientError, UpdateFailed):
                orders = list(self.data.orders) if self.data else []
                _LOGGER.warning("Failed to refresh orders; keeping previous data.")

            result.orders = orders
            result.active_order = _find_active_order(orders)
        elif self.data:
            # Carry forward stale data until the interval elapses
            result.orders = self.data.orders
            result.active_order = self.data.active_order

        return result
