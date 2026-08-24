"""Product discovery engine for the Azure Standard integration.

Analyses a user's ordered-packaged-products history and identifies products
they purchase frequently enough to warrant dedicated sensors.

The live API shape for each item in
``GET /person/{personId}/ordered-packaged-products`` is::

    {
        "code": "BK603",            # packaging / SKU code
        "productId": 28776,
        "orderCount": 1,            # total times ordered
        "lastOrderInvoiceDate": "2025-04-18",  # ISO date string
        "lastOrderId": 13624820
    }
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ProductStats dataclass
# ---------------------------------------------------------------------------


@dataclass
class ProductStats:
    """Parsed and enriched statistics for a single purchased product.

    Fields are derived from the live ``ordered-packaged-products`` API
    response.  Computed fields (``days_since_last_order``, ``is_candidate``)
    are populated by :class:`ProductDiscoveryEngine`.
    """

    code: str                           # packaging code, e.g. "CT123"
    product_id: int
    order_count: int                    # from API field ``orderCount``
    last_ordered: date | None           # from API field ``lastOrderInvoiceDate``
    last_order_id: int | None           # from API field ``lastOrderId``

    # Computed — not present in the raw API response
    days_since_last_order: int | None   # (today - last_ordered).days
    is_candidate: bool                  # order_count >= min_purchase_count


# ---------------------------------------------------------------------------
# ProductDiscoveryEngine
# ---------------------------------------------------------------------------


class ProductDiscoveryEngine:
    """Identify frequently-purchased products that are good sensor candidates.

    Usage::

        engine = ProductDiscoveryEngine(min_purchase_count=3)
        stats = engine.analyze(coordinator.data.ordered_products)
        new = engine.get_new_suggestions(stats, already_tracked={"CT123"})
    """

    def __init__(self, min_purchase_count: int = 3) -> None:
        self._min_purchase_count = min_purchase_count

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, ordered_products: list[dict[str, Any]]) -> list[ProductStats]:
        """Parse raw API items into :class:`ProductStats` objects.

        Items that cannot be parsed are skipped with a debug-level warning.
        The returned list is sorted by ``order_count`` descending so the most
        frequently ordered products appear first.

        :param ordered_products:
            Raw list returned by ``AzureStandardApiClient.get_ordered_products``.
        :returns:
            Sorted list of :class:`ProductStats`, including non-candidates
            (callers can filter on ``is_candidate``).
        """
        today = date.today()
        results: list[ProductStats] = []

        for item in ordered_products:
            stats = self._parse_item(item, today)
            if stats is not None:
                results.append(stats)

        results.sort(key=lambda s: s.order_count, reverse=True)
        return results

    def get_new_suggestions(
        self,
        stats: list[ProductStats],
        already_tracked: set[str],
    ) -> list[ProductStats]:
        """Return candidate products not yet tracked.

        A product is returned only when:
        - ``is_candidate`` is ``True`` (meets the ``min_purchase_count`` bar)
        - its ``code`` is not in ``already_tracked``

        :param stats: Output of :meth:`analyze`.
        :param already_tracked: Set of packaging codes the user has already
            confirmed as tracked sensors.
        :returns: Filtered list in the same order as *stats* (already sorted
            by order_count descending).
        """
        return [
            s for s in stats
            if s.is_candidate and s.code not in already_tracked
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_item(
        self,
        item: dict[str, Any],
        today: date,
    ) -> ProductStats | None:
        """Parse a single raw API item into a :class:`ProductStats`.

        Returns ``None`` if required fields are missing or unparseable.
        """
        code = item.get("code")
        if not code:
            _LOGGER.debug("Skipping ordered-product item with no 'code': %s", item)
            return None

        try:
            product_id = int(item.get("productId") or 0)
        except (TypeError, ValueError):
            product_id = 0

        try:
            order_count = int(item.get("orderCount") or 0)
        except (TypeError, ValueError):
            order_count = 0

        last_ordered = _parse_date(item.get("lastOrderInvoiceDate"))

        try:
            last_order_id_raw = item.get("lastOrderId")
            last_order_id = int(last_order_id_raw) if last_order_id_raw is not None else None
        except (TypeError, ValueError):
            last_order_id = None

        days_since = (today - last_ordered).days if last_ordered else None
        is_candidate = order_count >= self._min_purchase_count

        return ProductStats(
            code=str(code),
            product_id=product_id,
            order_count=order_count,
            last_ordered=last_ordered,
            last_order_id=last_order_id,
            days_since_last_order=days_since,
            is_candidate=is_candidate,
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date string to :class:`datetime.date`, or return ``None``."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
