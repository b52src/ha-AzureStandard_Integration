"""Azure Standard API client."""
from __future__ import annotations

import logging
from http.cookiejar import CookieJar
from typing import Any

import aiohttp

from .const import API_BASE

_LOGGER = logging.getLogger(__name__)

# The Azure Standard session cookie name
_SESSION_COOKIE_NAME = "id"
_AZURE_DOMAIN = "api.azurestandard.com"


class AzureStandardApiClient:
    """Async HTTP client for the Azure Standard REST API.

    Public methods need no authentication.  Auth-required methods use a
    cookie-based session obtained via :meth:`login`.

    The session cookie can be extracted after login with :meth:`extract_cookie`
    and restored on a subsequent HA startup with :meth:`restore_cookie`, so
    users are not forced to re-enter credentials after a restart.
    """

    BASE_URL = API_BASE

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Issue a GET request and return the parsed JSON response."""
        url = f"{self.BASE_URL}{path}"
        async with self._session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        """Issue a POST request and return the parsed JSON response."""
        url = f"{self.BASE_URL}{path}"
        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ------------------------------------------------------------------
    # Cookie management
    # ------------------------------------------------------------------

    def extract_cookie(self) -> str:
        """Return the raw session cookie value, or an empty string if not set.

        Call this after a successful :meth:`login` to persist the token in the
        config entry so HA can restore the session after a restart.
        """
        jar = self._session.cookie_jar
        for cookie in jar:
            if cookie.key == _SESSION_COOKIE_NAME and _AZURE_DOMAIN in (
                cookie.get("domain") or ""
            ):
                return cookie.value
        # Fallback: iterate all cookies without domain filter
        for cookie in jar:
            if cookie.key == _SESSION_COOKIE_NAME:
                return cookie.value
        return ""

    def restore_cookie(self, cookie_value: str) -> None:
        """Inject a previously-persisted session cookie into the aiohttp jar.

        This allows the coordinator to resume an authenticated session after
        an HA restart without asking the user to log in again.
        """
        if not cookie_value:
            return
        jar = self._session.cookie_jar
        # aiohttp's CookieJar accepts Morsel-like objects; the simplest way to
        # inject a raw value is via update_cookies with a plain dict.
        jar.update_cookies(
            {_SESSION_COOKIE_NAME: cookie_value},
            response_url=aiohttp.client.URL(f"https://{_AZURE_DOMAIN}/"),
        )

    # ------------------------------------------------------------------
    # Public endpoints (no auth required)
    # ------------------------------------------------------------------

    async def get_drop_id_for_person(self, person_id: int) -> int | None:
        """Return the drop ID for a person via the drop-memberships endpoint.

        Confirmed endpoint: GET /drop-memberships?filter-person={personId}
        Response shape: [{"drop": 2873, "customer": 1674720, "active": true}]
        Returns None if the person has no active membership.
        """
        try:
            data = await self._get(
                "/drop-memberships", params={"filter-person": person_id}
            )
            # API returns a list of membership dicts
            if isinstance(data, list):
                for entry in data:
                    if entry.get("active"):
                        return int(entry["drop"])
                if data:
                    return int(data[0]["drop"])
            elif isinstance(data, dict):
                return int(data["drop"])
        except (aiohttp.ClientError, KeyError, TypeError, ValueError):
            _LOGGER.debug("Could not fetch drop membership for person %d", person_id)
        return None

    async def get_drop_from_list(self, drop_id: int) -> dict | None:
        """Find a single drop by scanning paginated GET /drops.

        GET /drops/{id} returns 404.  The list endpoint paginates with a
        maximum of 250 per page; we page through until we find the drop or
        exhaust the results.

        Confirmed drop shape keys include: id, name, geo, order-frequency,
        active, address.
        order-frequency item shape: {"cutoff": "YYYY-MM-DD", "orders": N, ...}
        """
        limit = 200
        start = 0
        while True:
            try:
                page: list[dict] = await self._get(
                    "/drops", params={"limit": limit, "start": start}
                )
            except aiohttp.ClientError as err:
                _LOGGER.debug("Could not fetch drops page start=%d: %s", start, err)
                return None

            if not isinstance(page, list) or not page:
                return None

            for d in page:
                if isinstance(d, dict) and d.get("id") == drop_id:
                    return d

            if len(page) < limit:
                # Last page — drop not found
                return None
            start += limit

    async def get_product(self, product_id: int) -> dict:
        """Return full detail for a single product."""
        return await self._get(f"/products/{product_id}")

    async def get_products_by_category(
        self, category_id: int, limit: int = 50
    ) -> list[dict]:
        """Return products for a given category, up to *limit* results."""
        return await self._get(
            "/products", params={"categoryId": category_id, "limit": limit}
        )

    async def get_product_price(self, packaging_code: str) -> float | None:
        """Return the current price for a packaging code, or None if not found."""
        try:
            data = await self._get(
                "/products", params={"packagingCode": packaging_code}
            )
            if isinstance(data, list) and data:
                packagings = data[0].get("packaging", [])
                for pkg in packagings:
                    if pkg.get("code") == packaging_code:
                        return float(pkg.get("price", 0))
        except aiohttp.ClientError:
            _LOGGER.debug("Could not fetch price for %s", packaging_code)
        return None

    # ------------------------------------------------------------------
    # Auth-required endpoints
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> bool:
        """Authenticate and store the session cookie. Returns True on success.

        The Azure Standard API requires the field name ``username`` (not
        ``email``) in the login payload — confirmed by inspecting the 400
        error body: ``"JSON body missing value for username"``.
        """
        try:
            await self._post("/login", {"username": email, "password": password})
            return True
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                return False
            raise

    async def logout(self) -> None:
        """Invalidate the current session."""
        try:
            await self._post("/logout", {})
        except aiohttp.ClientError:
            pass  # best-effort

    async def validate_session(self) -> bool:
        """Return True if the current session cookie is still valid."""
        try:
            await self._get("/session")
            return True
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                return False
            raise

    async def get_session(self) -> dict:
        """Return the current session payload (includes person.id and drop info)."""
        return await self._get("/session")

    async def get_person(self, person_id: int) -> dict:
        """Return profile data for a person, including default drop assignment."""
        return await self._get(f"/person/{person_id}")

    async def get_ordered_products(self, person_id: int) -> list[dict]:
        """Return all products ever ordered with purchase frequency metadata.

        Confirmed endpoint: GET /person/{personId}/ordered-packaged-products
        Item shape: {code, productId, orderCount, lastOrderInvoiceDate, lastOrderId}
        """
        return await self._get(f"/person/{person_id}/ordered-packaged-products")

    async def get_orders(self, person_id: int, limit: int = 100) -> list[dict]:
        """Return the order list for a person.

        Confirmed endpoint: GET /orders?filter-person={personId}&limit=N
        Order shape: {id, customerId, status, drop, trip, placed, shipped,
                      checkout-payment, lastApiUpdate}
        Status values observed: "open", "delivered-to-drop"
        """
        return await self._get(
            "/orders", params={"filter-person": person_id, "limit": limit}
        )

    async def get_order(self, order_id: int) -> dict:
        """Return a single order with all line items.

        Confirmed endpoint: GET /order/{id}
        """
        return await self._get(f"/order/{order_id}")

    async def get_product_lists(self, person_id: int) -> list[dict]:
        """Return the saved shopping list metadata for a customer.

        Confirmed endpoint: GET /v2/products/product_lists?customerNumber={personId}
        Each list entry has at minimum: {id, name, ...}
        Items are fetched separately via get_product_list_items().
        """
        try:
            return await self._get(
                "/v2/products/product_lists",
                params={"customerNumber": person_id},
            )
        except aiohttp.ClientResponseError as err:
            if err.status == 404:
                _LOGGER.debug(
                    "Shopping list endpoint returned 404; returning empty list."
                )
                return []
            raise

    async def get_product_list_items(self, list_id: int) -> list[dict]:
        """Return items for a single shopping list.

        Confirmed endpoint: GET /v2/products/product_lists/{listId}/items
        Item shape: {id, productList, quantity, isPinned, pieceMetaId, slug,
                     image, name, directReplacement, createdAt, productCode}
        """
        return await self._get(f"/v2/products/product_lists/{list_id}/items")

    async def get_account_balance(self, person_id: int) -> list[dict]:
        """Return the latest account entry including running balance.

        Confirmed endpoint:
          GET /account-entries?filter-person={personId}&balance=true&limit=1&start=-1
        Response: [{id, person, amount, date, notes, balance}]
        """
        return await self._get(
            "/account-entries",
            params={
                "filter-person": person_id,
                "balance": "true",
                "limit": 1,
                "start": -1,
            },
        )

    async def get_spend_metrics(self, person_id: int) -> dict:
        """Return total spend and order counts."""
        return await self._get(
            "/accounts_receivable/spend-metrics",
            params={"filter-person": person_id},
        )
