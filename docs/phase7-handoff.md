# Azure Standard Integration — Phase 7 Handoff Context

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
| 6 | Product discovery engine: discovery.py, ProductStats, ProductDiscoveryEngine, HA notification | ✅ Done |
| **7** | **Product sensors: per-product sensor group (last_ordered, times_ordered, days_since, reorder_due)** | **⬅ NEXT** |
| 8 | Options flow product management: checkbox UI, dynamic entity creation | Pending |
| 9 | Account sensors: AccountCredit, PendingPayment | Pending |
| 10 | Polish: translations, icons, README | Pending |

---

## Confirmed API Endpoints (live-tested, August 2025)

See `docs/api-reference.md` for full details. Key facts for phase 7:

### Ordered Products
- `GET /person/{personId}/ordered-packaged-products`
- Item shape: `{code, productId, orderCount, lastOrderInvoiceDate, lastOrderId}`
- 124 products confirmed for personId=1674720
- Live example: `code=SW033, orderCount=20, lastOrderInvoiceDate="2026-06-19"`

### Shopping Lists (v2 base URL)
- `GET /v2/products/product_lists?customerNumber={personId}` → list metadata
- `GET /v2/products/product_lists/{listId}/items` → items with `{productCode, name, slug, quantity, isPinned}`

---

## File Structure

```
custom_components/azure_standard/
├── __init__.py          — setup/unload entry, PLATFORMS = [SENSOR, BINARY_SENSOR]
├── api.py               — AzureStandardApiClient (all methods corrected)
├── binary_sensor.py     — OrderWindowOpenBinarySensor
├── config_flow.py       — AzureStandardConfigFlow (mode→manual or account→drop_confirm)
├── const.py             — all constants including CONF_TRACKED_PRODUCTS, CONF_MIN_PURCHASE_COUNT
├── coordinator.py       — AzureStandardCoordinator + AzureStandardData (phase 6 updated)
├── discovery.py         — ProductStats, ProductDiscoveryEngine (new in phase 6)
├── entity.py            — AzureStandardEntity base class
├── manifest.json        — HA integration manifest
├── sensor.py            — all sensors including ShoppingListSensor
├── strings.json         — UI strings
└── translations/en.json — English translations

docs/
├── api-reference.md     — FULLY UPDATED with all confirmed endpoint corrections
├── architecture.md      — developer architecture reference
├── phase7-handoff.md    — this file
└── proposal.md          — full build plan (phases 1–10)

test_credentials.py      — smoke test (10 checks, all passing)
.venv/                   — Python venv with aiohttp
```

---

## Key Implementation Details

### discovery.py — ProductStats and ProductDiscoveryEngine

```python
@dataclass
class ProductStats:
    code: str                           # packaging code, e.g. "CT123"
    product_id: int
    order_count: int                    # from API field "orderCount"
    last_ordered: date | None           # from API field "lastOrderInvoiceDate"
    last_order_id: int | None
    days_since_last_order: int | None   # computed: (today - last_ordered).days
    is_candidate: bool                  # order_count >= min_purchase_count

class ProductDiscoveryEngine:
    def analyze(self, ordered_products: list[dict]) -> list[ProductStats]: ...
    def get_new_suggestions(self, stats, already_tracked: set[str]) -> list[ProductStats]: ...
```

### coordinator.py — AzureStandardData

```python
@dataclass
class AzureStandardData:
    drop: dict | None
    next_cutoff: date | None
    delivery_date: date | None
    active_order: dict | None
    orders: list[dict]
    product_lists: list[dict]          # each has embedded "items" list
    ordered_products: list[dict]       # raw from /ordered-packaged-products
    account_credit: float | None
    pending_payment: float | None
    product_stats: dict[str, ProductStats]   # keyed by code (added in phase 6)
    suggested_products: list[ProductStats]   # filtered candidates (added in phase 6)
    tracked_products: list[str]
    newly_confirmed_products: list[str]
```

### Config entry options (phase 8 will add UI, but data shape matters now)

```python
entry.options = {
    "tracked_products": ["SW033", "CT123"],   # list of packaging codes
    "min_purchase_count": 3,
}
```

### Sensor naming convention

Product sensor entity IDs follow the pattern:
```
sensor.azure_standard_{code}_{metric}
# e.g. sensor.azure_standard_sw033_times_ordered
```

---

## Phase 7 Specification

**Goal:** Add per-product sensor entities for each tracked product.

### Sensors to create per tracked product

Each code in `entry.options["tracked_products"]` gets a group of 4 sensors:

| Sensor class | unique_id suffix | state | unit |
|---|---|---|---|
| `ProductLastOrderedSensor` | `{code}_last_ordered` | ISO date string `"YYYY-MM-DD"` | — |
| `ProductTimesOrderedSensor` | `{code}_times_ordered` | integer count | `"orders"` |
| `ProductDaysSinceSensor` | `{code}_days_since` | integer days | `"d"` |
| `ProductReorderDueSensor` | `{code}_reorder_due` | `"true"` / `"false"` | — |

`ProductReorderDueSensor` fires `"true"` when `days_since_last_order` exceeds a configurable threshold (or a hardcoded default of 30 days for now — phase 8 will add per-product thresholds). This can also be a `BinarySensor` — your call.

### Implementation approach

1. **`sensor.py`**: Add `ProductLastOrderedSensor`, `ProductTimesOrderedSensor`, `ProductDaysSinceSensor` (plus either `ProductReorderDueSensor` or a binary sensor version).

2. **`coordinator.py`**: In the history block, after populating `product_stats`, check `entry.options["tracked_products"]` and add any newly-tracked product sensors via `_platform_callbacks[Platform.SENSOR]` (same pattern as `ShoppingListSensor`).

3. **Dynamic entity creation**: On first load and after each history refresh, compare `tracked_products` from options against `_known_product_codes` on the coordinator. If there are new codes present in `product_stats`, call `async_add_entities` for the 4-sensor group.

### State source

All product sensors read from `coordinator.data.product_stats[code]` (a `ProductStats` object). If the code is not in `product_stats` (e.g. history hasn't loaded yet), return `STATE_UNKNOWN`.

### Sensor base class

Product sensors should inherit from `AzureStandardEntity` (already in `entity.py`). The `_attr_unique_id` should be `f"{DOMAIN}_{code.lower()}_{metric}"`.

### Test additions

Add check [11] to `test_credentials.py`:
```
[11] Sensor state simulation — for code SW033, construct a fake ProductStats
     and verify that each of the 4 sensor "state" methods would return valid values.
     (Pure Python — no HA runtime needed, no network call.)
```

---

## Test Command

```bash
cd /Users/seancrow/Forgejo/AzureStandard_Intigration
AZ_EMAIL=b52src@gmail.com AZ_PASSWORD='P@$790rd052' .venv/bin/python3 test_credentials.py
```

All 10 checks currently pass.

## Syntax check command

```bash
.venv/bin/python3 -m py_compile \
  custom_components/azure_standard/api.py \
  custom_components/azure_standard/coordinator.py \
  custom_components/azure_standard/config_flow.py \
  custom_components/azure_standard/sensor.py \
  custom_components/azure_standard/const.py \
  custom_components/azure_standard/discovery.py
```
