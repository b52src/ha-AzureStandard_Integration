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

    async def get_drops(self) -> list[dict]:
        """Return all drop locations with their cutoff schedules."""
        return await self._get("/drops")

    async def get_drop(self, drop_id: int) -> dict:
        """Return a single drop by ID with its full cutoff schedule."""
        return await self._get(f"/drops/{drop_id}")

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
        """Authenticate and store the session cookie. Returns True on success."""
        try:
            await self._post("/login", {"email": email, "password": password})
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

    async def get_ordered_products(self) -> list[dict]:
        """Return all products ever ordered with purchase frequency metadata."""
        return await self._get("/ordered-packaged-products")

    async def get_orders(self) -> list[dict]:
        """Return the order list with status, cutoff date, and totals."""
        return await self._get("/orders/orders")

    async def get_order(self, order_id: int) -> dict:
        """Return a single order with all line items."""
        return await self._get(f"/order/{order_id}")

    async def get_product_lists(self) -> list[dict]:
        """Return saved shopping lists with items and quantities."""
        return await self._get("/products/product_lists")

    async def get_account_entries(self) -> list[dict]:
        """Return credit balance, invoices, and payment records."""
        return await self._get("/account-entries")

    async def get_spend_metrics(self) -> dict:
        """Return total spend and order counts."""
        return await self._get("/accounts_receivable/spend-metrics")

    async def get_pending_payments(self) -> dict:
        """Return outstanding payment state."""
        return await self._get("/accounts_receivable/pending-payments-state")
