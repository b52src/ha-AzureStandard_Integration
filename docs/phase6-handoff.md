# Azure Standard Integration — Phase 6 Handoff Context

## Goal

Build a complete Home Assistant custom integration for Azure Standard (organic food co-op delivery).
The integration monitors drop cutoff dates, orders, shopping lists, and purchase history.
Being built phase by phase per the spec in `docs/proposal.md`.

---

## Build Plan Status

| Phase | Description | Status |
|---|---|---|
| 1 | Core scaffold: manifest, const, __init__, entity, api (public), strings | ✅ Done |
| 2 | Drop & cutoff sensors: coordinator, NextCutoff, DaysUntilCutoff, DropName, DeliveryDate, OrderWindowOpen | ✅ Done |
| 3 | Account login: config_flow (mode select, manual, account, drop_confirm steps) | ✅ Done |
| 4 | Order sensors: ActiveOrderStatus, ActiveOrderItemCount, ActiveOrderTotal, LastOrderDate | ✅ Done |
| 5 | Shopping list sensors: ShoppingListSensor (dynamic), coordinator list polling | ✅ Done |
| **6** | **Product discovery engine: discovery.py, ProductStats, ProductDiscoveryEngine, HA notification** | **⬅ NEXT** |
| 7 | Product sensors: per-product sensor group (last_ordered, times_ordered, avg_interval, days_until_reorder, current_price) | Pending |
| 8 | Options flow product management: checkbox UI, dynamic entity creation, price history HA storage | Pending |
| 9 | Account sensors: AccountCredit, PendingPayment | Pending |
| 10 | Polish: translations, icons, README | Pending |

---

## Confirmed API Endpoints (live-tested, August 2025)

All findings are documented in full at `docs/api-reference.md`.

### Authentication
- `POST /login` with body `{"username": "...", "password": "..."}` — field is **`username`** not `email`
- Session cookie name: `id`
- Session response: `{"personId": 1674720, "person": 1674720}` — `person` is an **integer**, not a nested dict

### Drop
- `GET /drops/{id}` → **404** (broken)
- Drop cutoff: `GET /drops?limit=200&start=0` (paginated, max 250/page) — scan for `d.get("id") == drop_id`
- Drop membership: `GET /drop-memberships?filter-person={personId}` → `[{"drop": 2873, "customer": ..., "active": true}]`
- Drop shape: `{id, name, geo, active, order-frequency: [{cutoff: "YYYY-MM-DD", orders: N, homeDeliveryOrders: []}]}`
- **No delivery date** in drop response

### Orders
- `GET /orders?filter-person={personId}&limit=100` — confirmed working
- Order shape: `{id, customerId, status, drop, trip, placed, shipped, checkout-payment, lastApiUpdate}`
- Confirmed status values: `"open"`, `"delivered-to-drop"`
- **No `cutoffDate`, `total`, or `items`** in the list response
- `GET /order/{id}` — single order confirmed working

### Ordered Products (purchase history)
- `GET /person/{personId}/ordered-packaged-products` — confirmed, 124 products
- Item shape: `{code, productId, orderCount, lastOrderInvoiceDate, lastOrderId}`
- **Fields that do NOT exist** (were in original proposal but absent from live API):
  `quantity-ordered`, `last-order-placed`, `first-order-placed`, `orderRecency`,
  `packaging.next-purchase-arrival`, `packaging.vendorShortedLastPurchase`

### Account
- `GET /account-entries?filter-person={personId}&balance=true&limit=1&start=-1`
  → `[{id, person, amount, date, notes, balance}]` — `balance` field confirmed (not `runningBalance`)

### Shopping Lists (v2 base URL)
- `GET /v2/products/product_lists?customerNumber={personId}` → 11 lists, each with `{id, name, ...}`
- `GET /v2/products/product_lists/{listId}/items` → `[{id, productList, quantity, isPinned, pieceMetaId, slug, image, name, directReplacement, createdAt, productCode}]`

---

## File Structure

```
custom_components/azure_standard/
├── __init__.py          — setup/unload entry, PLATFORMS = [SENSOR, BINARY_SENSOR]
├── api.py               — AzureStandardApiClient (all methods corrected)
├── binary_sensor.py     — OrderWindowOpenBinarySensor
├── config_flow.py       — AzureStandardConfigFlow (mode→manual or account→drop_confirm)
├── const.py             — all constants, including CONF_PERSON_ID (new)
├── coordinator.py       — AzureStandardCoordinator + AzureStandardData
├── entity.py            — AzureStandardEntity base class
├── manifest.json        — HA integration manifest
├── sensor.py            — all sensors including ShoppingListSensor
├── strings.json         — UI strings
└── translations/en.json — English translations

docs/
├── api-reference.md     — FULLY UPDATED with all confirmed endpoint corrections
├── architecture.md      — developer architecture reference
└── proposal.md          — full build plan (phases 1–10)

test_credentials.py      — smoke test (9 checks, all passing)
.venv/                   — Python venv with aiohttp
```

---

## Key Implementation Details

### Config Entry Data Schema (account mode)
```python
{
    "mode": "account",
    "email": "user@example.com",
    "drop_id": 2873,
    "person_id": 1674720,       # NEW in phase 5 — required for all account API calls
    "session_cookie": "<token>"
}
```

### coordinator.py: AzureStandardData dataclass
```python
@dataclass
class AzureStandardData:
    drop: dict | None = None
    next_cutoff: date | None = None
    delivery_date: date | None = None          # always None currently (not in API)
    active_order: dict | None = None
    orders: list[dict] = field(default_factory=list)
    product_lists: list[dict] = field(default_factory=list)  # each has embedded "items" list
    ordered_products: list[dict] = field(default_factory=list)  # NOT YET POPULATED
    account_credit: float | None = None
    pending_payment: float | None = None
    product_stats: dict[str, Any] = field(default_factory=dict)   # keyed by code
    suggested_products: list[Any] = field(default_factory=list)
    tracked_products: list[str] = field(default_factory=list)
    newly_confirmed_products: list[str] = field(default_factory=list)
```

### coordinator.py: Key methods
- `coordinator.person_id` → `entry.data.get("person_id")` — used in all account API calls
- `_find_active_order(orders)` — uses `"placed"` field for sorting, substring terminal detection (`"cancel"`, `"refund"`, `"delivered"`)
- `_find_next_cutoff(drop)` — reads `order-frequency[].cutoff` only (no delivery date)
- `_extract_credit(entries)` — reads `entries[0]["balance"]`
- Shopping list fetch: gets metadata list → for each list, fetches items → embeds as `{**lst, "items": items}`

### api.py: Important method signatures
```python
get_drop_from_list(drop_id: int) -> dict | None         # paginated /drops scan
get_drop_id_for_person(person_id: int) -> int | None    # /drop-memberships
get_orders(person_id: int, limit=100) -> list[dict]     # /orders?filter-person=
get_ordered_products(person_id: int) -> list[dict]      # /person/{id}/ordered-packaged-products
get_product_lists(person_id: int) -> list[dict]         # /v2/products/product_lists
get_product_list_items(list_id: int) -> list[dict]      # /v2/products/product_lists/{id}/items
get_account_balance(person_id: int) -> list[dict]       # /account-entries?balance=true
```

---

## Phase 6 Specification

**Goal:** Build `discovery.py` — the `ProductDiscoveryEngine` and `ProductStats` dataclass.

### What phase 6 must deliver

1. **`custom_components/azure_standard/discovery.py`** — new file containing:
   - `ProductStats` dataclass
   - `ProductDiscoveryEngine` class

2. **`coordinator.py`** update:
   - Add `ordered_products` fetch to `_async_update_data` (using `SCAN_INTERVAL_HISTORY` / 24h)
   - Call `ProductDiscoveryEngine.analyze()` and populate `data.product_stats`, `data.suggested_products`
   - Fire HA persistent notification when new product candidates are found

3. **`const.py`** additions needed:
   - `SCAN_INTERVAL_HISTORY = timedelta(hours=24)` — already present
   - `DEFAULT_MIN_PURCHASE_COUNT = 3` — already present
   - `DEFAULT_SALE_THRESHOLD = 0.95` — already present

### ProductStats dataclass (adapt from proposal — use REAL field names)

The live API `ordered-packaged-products` response gives:
```python
{
    "code": "BK603",          # packaging code
    "productId": 28776,
    "orderCount": 1,          # total times ordered — this IS the field name
    "lastOrderInvoiceDate": "2025-04-18",  # ISO date string
    "lastOrderId": 13624820
}
```

**Fields that DON'T exist** (were in original proposal but absent):
- `quantity-ordered` → use `orderCount` instead
- `last-order-placed` → use `lastOrderInvoiceDate` instead
- `first-order-placed` → not available; skip or derive from order history
- `orderRecency` → not available; derive from `lastOrderInvoiceDate`

**Adapted ProductStats:**
```python
@dataclass
class ProductStats:
    code: str                                  # packaging code, e.g. "CT123"
    product_id: int
    order_count: int                           # total times purchased (from orderCount)
    last_ordered: date | None                  # from lastOrderInvoiceDate
    last_order_id: int | None
    # Computed fields (not from API):
    days_since_last_order: int | None          # today - last_ordered
    is_candidate: bool                         # order_count >= MIN_PURCHASE_COUNT
```

### Discovery engine requirements

```python
class ProductDiscoveryEngine:
    def __init__(self, min_purchase_count: int = 3): ...
    
    def analyze(self, ordered_products: list[dict]) -> list[ProductStats]:
        """Parse raw API items → ProductStats list, filter to candidates."""
        ...
    
    def get_new_suggestions(
        self,
        stats: list[ProductStats],
        already_tracked: set[str],
    ) -> list[ProductStats]:
        """Return stats for products not yet tracked and meeting the evidence bar."""
        ...
```

### Coordinator integration

In `_async_update_data`, add a new interval block (piggyback on a `_history_due()` check at `SCAN_INTERVAL_HISTORY`):

```python
if self._history_due():
    self._last_history_fetch = datetime.now()
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
    
    tracked = set(self.entry.options.get(CONF_TRACKED_PRODUCTS, []))
    new_suggestions = engine.get_new_suggestions(stats, tracked)
    result.suggested_products = new_suggestions
    
    # Fire HA notification if there are new suggestions not previously seen
    if new_suggestions:
        _fire_suggestion_notification(self.hass, new_suggestions)
```

### HA persistent notification

Use `hass.components.persistent_notification.async_create`:
```python
hass.components.persistent_notification.async_create(
    f"Azure Standard found {len(new_suggestions)} products you order regularly "
    f"that could have sensors created. Configure in the integration options.",
    title="Azure Standard — Product Suggestions",
    notification_id="azure_standard_product_suggestions",
)
```

---

## Test Command

```bash
cd /Users/seancrow/Forgejo/AzureStandard_Intigration
AZ_EMAIL=b52src@gmail.com AZ_PASSWORD='P@$790rd052' .venv/bin/python3 test_credentials.py
```

All 9 checks currently pass. Phase 6 should add a check [10] to the test script:
```
[10] Ordered products stats analysis (no network call — just parse the 124 products)
```

## Syntax check command

```bash
.venv/bin/python3 -m py_compile \
  custom_components/azure_standard/api.py \
  custom_components/azure_standard/coordinator.py \
  custom_components/azure_standard/config_flow.py \
  custom_components/azure_standard/sensor.py \
  custom_components/azure_standard/const.py \
  custom_components/azure_standard/discovery.py  # new file
```
