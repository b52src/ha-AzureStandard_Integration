"""Data coordinator for the Azure Standard integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.components import persistent_notification
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
    CONF_MIN_PURCHASE_COUNT,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PERSON_ID,
    CONF_SESSION_COOKIE,
    CONF_TRACKED_PRODUCTS,
    DEFAULT_MIN_PURCHASE_COUNT,
    DOMAIN,
    MODE_ACCOUNT,
    MODE_MANUAL,
    SCAN_INTERVAL_HISTORY,
    SCAN_INTERVAL_LISTS,
    SCAN_INTERVAL_ORDERS,
    SCAN_INTERVAL_PUBLIC,
    SCAN_INTERVAL_SESSION,
)
from .discovery import ProductDiscoveryEngine

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
    """Extract the nearest future cutoff from a drop dict.

    Confirmed order-frequency shape from live API:
      {"cutoff": "YYYY-MM-DD", "orders": N, "homeDeliveryOrders": [...]}

    No delivery date is present in the public /drops response.  We return
    ``None`` for the delivery date; a future phase may fetch it from the
    trip endpoint.

    Returns ``(next_cutoff_date, delivery_date)``.
    """
    today = date.today()
    best_cutoff: date | None = None

    for freq in drop.get("order-frequency", []):
        if not isinstance(freq, dict):
            continue
        cutoff = _parse_date(freq.get("cutoff"))
        if cutoff is None or cutoff < today:
            continue
        if best_cutoff is None or cutoff < best_cutoff:
            best_cutoff = cutoff

    return best_cutoff, None


# ---------------------------------------------------------------------------
# Order helpers
# ---------------------------------------------------------------------------


def _find_active_order(orders: list[dict]) -> dict | None:
    """Return the most recent non-terminal order, or None.

    Confirmed status values from the live API:
      "open"                 — order is being built
      "delivered-to-drop"    — order has arrived at the drop

    We treat anything that is NOT a clearly terminal state as active.
    The terminal set uses substring matching so future variants like
    "delivered-to-customer" are also caught.
    """
    def _is_terminal(status: str) -> bool:
        s = status.lower()
        return any(t in s for t in ("cancel", "refund", "delivered"))

    candidates = [o for o in orders if not _is_terminal(o.get("status", ""))]
    if not candidates:
        return None
    # Sort by placed date descending; fall back to id descending
    return max(
        candidates,
        key=lambda o: o.get("placed") or str(o.get("id", "")),
    )


def _extract_credit(account_entries: list[dict]) -> float | None:
    """Return the current account credit balance.

    Confirmed field name from live API: ``balance`` (not ``runningBalance``).
    We fetch only the latest entry (limit=1, start=-1) so the list has exactly
    one element.
    """
    if not account_entries:
        return None
    last = account_entries[0]  # latest entry is first when fetched with start=-1
    for key in ("balance", "runningBalance"):
        raw = last.get(key)
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
    return None


# ---------------------------------------------------------------------------
# HA notification helper
# ---------------------------------------------------------------------------


def _fire_suggestion_notification(hass: Any, suggestions: list[Any]) -> None:
    """Fire a persistent notification listing new product suggestions.

    Uses a stable ``notification_id`` so repeated calls with the same
    products collapse to a single notification rather than creating duplicates.
    """
    count = len(suggestions)
    codes = ", ".join(s.code for s in suggestions[:5])
    if count > 5:
        codes += f" … and {count - 5} more"

    persistent_notification.async_create(
        hass,
        (
            f"Azure Standard found **{count} product{'s' if count != 1 else ''}** "
            f"you order regularly that could have dedicated sensors created:\n\n"
            f"{codes}\n\n"
            "Open the integration options to choose which products to track."
        ),
        title="Azure Standard — Product Suggestions",
        notification_id="azure_standard_product_suggestions",
    )


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

        # Tracking sets for dynamic entity creation
        self._known_list_ids: set[str] = set()
        self._known_product_codes: set[str] = set()

        # Timestamps controlling account-data sub-intervals
        self._last_orders_fetch: datetime | None = None
        self._last_lists_fetch: datetime | None = None
        self._last_session_check: datetime | None = None
        self._last_history_fetch: datetime | None = None

        # Restore the session cookie from entry.data so the client is
        # immediately authenticated without a re-login after HA restart.
        if entry.data.get(CONF_MODE) == MODE_ACCOUNT:
            cookie = entry.data.get(CONF_SESSION_COOKIE, "")
            if cookie:
                self.client.restore_cookie(cookie)

    @property
    def person_id(self) -> int | None:
        """Return the authenticated person's numeric ID, or None in manual mode."""
        return self.entry.data.get(CONF_PERSON_ID)

    def register_platform_callback(self, platform: Platform, callback: Any) -> None:
        """Register an *async_add_entities* callback for a platform."""
        self._platform_callbacks[platform] = callback

    # ------------------------------------------------------------------
    # Re-authentication helper
    # ------------------------------------------------------------------

    async def _reauth(self) -> None:
        """Attempt to re-authenticate using stored credentials.

        If a password is stored in entry.data, performs a silent re-login and
        updates the session cookie without any user interaction.

        Raises :class:`ConfigEntryAuthFailed` only when no password is stored
        (e.g. entries created before this version), which prompts the HA repair
        UI to ask the user to re-enter credentials via the reauth flow.
        """
        email = self.entry.data.get(CONF_EMAIL)
        password = self.entry.data.get(CONF_PASSWORD)

        if not email or not password:
            _LOGGER.warning(
                "Azure Standard session expired for %s — no stored password, "
                "reauthentication required via the UI.",
                email,
            )
            raise ConfigEntryAuthFailed(
                f"Session expired for {email}. Please reconfigure the integration."
            )

        _LOGGER.info(
            "Azure Standard session expired for %s — attempting silent re-login.",
            email,
        )
        try:
            success = await self.client.login(email, password)
        except aiohttp.ClientError as err:
            raise ConfigEntryAuthFailed(
                f"Could not reach Azure Standard API during re-login: {err}"
            ) from err

        if not success:
            raise ConfigEntryAuthFailed(
                f"Re-login failed for {email} — password may have changed. "
                "Please reconfigure the integration."
            )

        # Persist the fresh session cookie so it survives an HA restart
        new_cookie = self.client.extract_cookie()
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={**self.entry.data, CONF_SESSION_COOKIE: new_cookie},
        )
        _LOGGER.info("Azure Standard re-login successful for %s.", email)

    async def _authenticated_get(self, coro_factory) -> Any:
        """Execute *coro_factory()* and retry once after re-auth on 401/403.

        If the retry also gets a 401/403, raises :class:`ConfigEntryAuthFailed`
        so the error propagates past the catch-and-swallow blocks in
        ``_async_update_data`` and reaches HA's coordinator machinery.

        :param coro_factory: Zero-argument callable that returns a coroutine.
        """
        try:
            return await coro_factory()
        except aiohttp.ClientResponseError as err:
            if err.status not in (401, 403):
                raise
            await self._reauth()
            try:
                return await coro_factory()
            except aiohttp.ClientResponseError as retry_err:
                if retry_err.status in (401, 403):
                    raise ConfigEntryAuthFailed(
                        "Re-authenticated but requests are still being rejected. "
                        "Please reconfigure the integration."
                    ) from retry_err
                raise

    # ------------------------------------------------------------------
    # Sub-interval predicates
    # ------------------------------------------------------------------

    def _history_due(self) -> bool:
        if self._last_history_fetch is None:
            return True
        return datetime.now() - self._last_history_fetch >= SCAN_INTERVAL_HISTORY

    def _orders_due(self) -> bool:
        if self._last_orders_fetch is None:
            return True
        return datetime.now() - self._last_orders_fetch >= SCAN_INTERVAL_ORDERS

    def _lists_due(self) -> bool:
        if self._last_lists_fetch is None:
            return True
        return datetime.now() - self._last_lists_fetch >= SCAN_INTERVAL_LISTS

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

        # ---- Public data: drop schedule (always fetched) ----
        # GET /drops/{id} returns 404; scan the full list instead.
        try:
            drop = await self.client.get_drop_from_list(drop_id)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching drops list: {err}") from err

        if drop is None:
            # Keep previous drop data rather than wiping sensors
            drop = (self.data.drop if self.data else None) or {}

        next_cutoff, delivery_date = _find_next_cutoff(drop)

        result = AzureStandardData(
            drop=drop,
            next_cutoff=next_cutoff,
            delivery_date=delivery_date,
        )

        if mode != MODE_ACCOUNT:
            return result

        pid = self.person_id
        if not pid:
            _LOGGER.warning("No person_id stored — skipping account data fetch.")
            return result

        # ---- Session health check (every SCAN_INTERVAL_SESSION) ----
        if self._session_check_due():
            self._last_session_check = datetime.now()
            try:
                valid = await self.client.validate_session()
            except aiohttp.ClientError:
                # Network error — skip reauth, the next update will retry
                valid = True
            if not valid:
                await self._reauth()

        # ---- Account data: orders (every SCAN_INTERVAL_ORDERS) ----
        if self._orders_due():
            self._last_orders_fetch = datetime.now()
            try:
                orders = await self._authenticated_get(
                    lambda: self.client.get_orders(pid)
                )
            except (aiohttp.ClientError, UpdateFailed):
                orders = list(self.data.orders) if self.data else []
                _LOGGER.warning("Failed to refresh orders; keeping previous data.")

            result.orders = orders
            result.active_order = _find_active_order(orders)
        elif self.data:
            result.orders = self.data.orders
            result.active_order = self.data.active_order

        # ---- Account credit balance ----
        if self._orders_due():  # piggyback on the orders interval
            try:
                entries = await self._authenticated_get(
                    lambda: self.client.get_account_balance(pid)
                )
                result.account_credit = _extract_credit(entries)
            except (aiohttp.ClientError, UpdateFailed):
                result.account_credit = self.data.account_credit if self.data else None
                _LOGGER.warning("Failed to refresh account balance; keeping previous.")
        elif self.data:
            result.account_credit = self.data.account_credit

        # ---- Purchase history + product discovery (every SCAN_INTERVAL_HISTORY) ----
        if self._history_due():
            self._last_history_fetch = datetime.now()
            try:
                ordered = await self._authenticated_get(
                    lambda: self.client.get_ordered_products(pid)
                )
                result.ordered_products = ordered

                engine = ProductDiscoveryEngine(
                    min_purchase_count=self.entry.options.get(
                        CONF_MIN_PURCHASE_COUNT, DEFAULT_MIN_PURCHASE_COUNT
                    )
                )
                stats = engine.analyze(ordered)
                result.product_stats = {s.code: s for s in stats}

                tracked: set[str] = set(
                    self.entry.options.get(CONF_TRACKED_PRODUCTS, [])
                )
                new_suggestions = engine.get_new_suggestions(stats, tracked)
                result.suggested_products = new_suggestions

                if new_suggestions:
                    _fire_suggestion_notification(self.hass, new_suggestions)

                # Notify the sensor platform about any newly-tracked product codes
                if Platform.SENSOR in self._platform_callbacks and tracked:
                    new_codes = tracked - self._known_product_codes
                    new_codes_with_stats = new_codes & result.product_stats.keys()
                    if new_codes_with_stats:
                        from .sensor import _make_product_sensors  # local import avoids cycle
                        new_entities = []
                        for code in new_codes_with_stats:
                            new_entities.extend(_make_product_sensors(self, code))
                        self._platform_callbacks[Platform.SENSOR](new_entities)
                        self._known_product_codes |= new_codes_with_stats

            except (aiohttp.ClientError, UpdateFailed):
                if self.data:
                    result.ordered_products = self.data.ordered_products
                    result.product_stats = self.data.product_stats
                    result.suggested_products = self.data.suggested_products
                _LOGGER.warning(
                    "Failed to refresh purchase history; keeping previous data."
                )
        elif self.data:
            result.ordered_products = self.data.ordered_products
            result.product_stats = self.data.product_stats
            result.suggested_products = self.data.suggested_products

        # ---- Shopping lists (every SCAN_INTERVAL_LISTS) ----
        if self._lists_due():
            self._last_lists_fetch = datetime.now()
            try:
                list_meta = await self._authenticated_get(
                    lambda: self.client.get_product_lists(pid)
                )
                # Fetch items for each list and embed them under an "items" key
                product_lists: list[dict] = []
                for lst in list_meta:
                    list_id = lst.get("id")
                    if list_id:
                        try:
                            items = await self._authenticated_get(
                                lambda lid=list_id: self.client.get_product_list_items(lid)
                            )
                            product_lists.append({**lst, "items": items})
                        except aiohttp.ClientError:
                            product_lists.append({**lst, "items": []})
                    else:
                        product_lists.append({**lst, "items": []})
            except (aiohttp.ClientError, UpdateFailed):
                product_lists = list(self.data.product_lists) if self.data else []
                _LOGGER.warning("Failed to refresh shopping lists; keeping previous.")

            result.product_lists = product_lists

            # Notify the sensor platform about any newly discovered lists
            if Platform.SENSOR in self._platform_callbacks:
                existing_ids: set[str] = getattr(self, "_known_list_ids", set())
                new_lists = [
                    lst
                    for lst in product_lists
                    if str(lst.get("id", "")) not in existing_ids
                ]
                if new_lists:
                    from .sensor import ShoppingListSensor  # local import avoids cycle
                    self._platform_callbacks[Platform.SENSOR](
                        [ShoppingListSensor(self, lst) for lst in new_lists]
                    )
                    self._known_list_ids = existing_ids | {
                        str(lst.get("id", "")) for lst in product_lists
                    }
        elif self.data:
            result.product_lists = self.data.product_lists

        return result
