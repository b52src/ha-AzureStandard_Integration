# Azure Standard — Home Assistant Integration Proposal

**Version:** 0.2 — August 2025  
**Status:** Draft / Pre-development

---

## Table of Contents

1. [API Findings](#1-api-findings)
2. [Authentication Model](#2-authentication-model)
3. [Confirmed Endpoints](#3-confirmed-endpoints)
4. [Setup Modes](#4-setup-modes)
5. [Smart Product Discovery Engine](#5-smart-product-discovery-engine)
6. [Proposed HA Entities](#6-proposed-ha-entities)
7. [Integration Architecture](#7-integration-architecture)
8. [Build Plan](#8-build-plan)
9. [Limitations & Risks](#9-limitations--risks)

---

## 1. API Findings

Azure Standard does not publish a public API, but their website is a JavaScript SPA (AngularJS) that consumes a REST API at `https://api.azurestandard.com`. It responds to plain HTTP requests with JSON.

**No auth needed:** Product listings, drop locations, upcoming cutoff date schedules, and current product prices.

**Auth required:** Cart, shopping lists, order history, ordered products, account info. Authentication uses **cookie-based sessions** — `POST /login` returns a session cookie `id` that is sent with all subsequent requests via `withCredentials: true`.

---

## 2. Authentication Model

```http
POST https://api.azurestandard.com/login
Content-Type: application/json

{ "email": "you@example.com", "password": "..." }

→ Set-Cookie: id=<session_token>; Domain=.azurestandard.com; Secure; HttpOnly

# All subsequent authenticated calls:
GET https://api.azurestandard.com/ordered-packaged-products
Cookie: id=<session_token>
```

The integration uses HA's `aiohttp` `CookieJar`, stores only the session token (never the raw password after first login), and re-authenticates automatically on 401.

---

## 3. Confirmed Endpoints

### Public — no auth needed

| Endpoint | Key Fields |
|---|---|
| `GET /drops` | `id`, `name`, `geo`, `active`, `order-frequency[].cutoff` (weekly cutoff dates ~6 months out) |
| `GET /drops/{id}` | Single drop with full cutoff schedule |
| `GET /products?categoryId={id}&limit={n}` | Products with `packaging[].code`, `price`, `stock`, `images` |
| `GET /products/{id}` | Full single-product detail |

### Authenticated

| Endpoint | Key Fields |
|---|---|
| `GET /session` | `person.email`, `person.order-place-issue`, drop assignment |
| `GET /person/{id}` | Profile, addresses, drop assignment |
| `GET /ordered-packaged-products` | `last-order-placed`, `first-order-placed`, `quantity-ordered`, `orderRecency`, `packaging.next-purchase-arrival`, `packaging.vendorShortedLastPurchase` |
| `GET /orders/orders` | Order list with status, cutoff date, trip/delivery date, totals |
| `GET /order/{id}` | Single order with all line items |
| `GET /products/product_lists` | Saved shopping lists with items + quantities |
| `GET /products/shop_product_lists` | Public/followed community lists |
| `GET /account-entries` | Credit balance, invoices, payments |
| `GET /accounts_receivable/spend-metrics` | Total spend, order counts |
| `GET /accounts_receivable/pending-payments-state` | Outstanding payment state |

---

## 4. Setup Modes

The integration config flow offers two paths:

### Mode A: Manual (No Account Login)

For users who only want drop/cutoff tracking. Requires only a **Drop ID** (numeric — find yours by searching `https://api.azurestandard.com/drops` and matching by name/location).

**Entities available:** Next cutoff date, days until cutoff, delivery date, order window binary sensor, drop name.

**Not available:** Shopping lists, order history, product sensors.

### Mode B: Account (Full Access)

Login with Azure Standard email + password. Drop is **auto-detected from your account's assigned default drop** with option to override.

**Entities available:** Everything in Mode A plus orders, shopping lists, product discovery sensors, account credit.

**Options flow (after setup):**
- Re-configure credentials / change drop
- Enable/disable smart product discovery
- Set minimum purchase count threshold (default: 3)
- Manage tracked product list — add/remove packaging codes

---

## 5. Smart Product Discovery Engine

Inspired by the learning/suggestion architecture in [ha_washdata](https://github.com/3dg1luk43/ha_washdata), the integration includes a `ProductDiscoveryEngine` that analyzes your purchase history and proposes dedicated HA sensors for frequently purchased products.

### Core concept

`GET /ordered-packaged-products` returns every product you've ever ordered, with fields:
- `last-order-placed` — most recent order date
- `first-order-placed` — oldest order date
- `quantity-ordered` — total units purchased
- `orderRecency` — recency indicator
- `packaging.next-purchase-arrival` — if re-ordered today, estimated arrival
- `packaging.vendorShortedLastPurchase` — whether the last order was shorted by the vendor

From this, the engine computes per-product statistics and surfaces sensor proposals.

### Statistical model (per product)

```python
@dataclass
class ProductStats:
    packaging_code: str           # e.g. "CT123"
    product_name: str
    total_orders: int             # total times purchased
    first_ordered: date
    last_ordered: date
    avg_days_between_orders: float | None   # None if < 2 orders
    median_days_between_orders: float | None
    price_history: list[tuple[date, float]] # (date, price) — rolling 90 days in HA storage
    current_price: float
    avg_price: float              # rolling average for on-sale detection
    is_on_sale: bool              # current_price < avg_price * SALE_THRESHOLD
    sale_discount_pct: float | None
    next_suggested_order_date: date | None  # last_ordered + avg_days_between_orders
    days_until_suggested_order: int | None  # sensor value (negative = overdue)
    was_shorted_last_purchase: bool
```

### Discovery flow

```
1. Coordinator fetches /ordered-packaged-products (every 24h)
   ↓
2. ProductDiscoveryEngine.analyze(products):
   - Filter: total_orders >= MIN_PURCHASE_COUNT (default 3)
   - Filter: not already a tracked sensor
   - Compute stats for each candidate
   ↓
3. New candidates → HA persistent notification:
   "Azure Standard: 5 frequently purchased products can have sensors created.
    [Manage in integration options →]"
   ↓
4. Options flow "Suggested Products" step:
   ┌─────────────────────────────────────────────────────────┐
   │ Product Name      Code    Orders  Avg Interval  On Sale │
   │ ✅ Canned Tomatoes CT123   12      21 days       No      │
   │ ✅ Olive Oil       OO456   8       35 days       YES -12%│
   │ ☐  Black Beans    BB789   3       —             No      │
   └─────────────────────────────────────────────────────────┘
   [Save] → entities created immediately, no HA restart required
```

### Minimum evidence bars (washdata-inspired guards)

Borrowed from washdata's `_CLEAN_MIN_DURATION_S` / `MIN_SUGGESTION_COOLDOWN_CYCLES` pattern — do not propose sensors for products that don't have sufficient purchase history:

```python
MIN_PURCHASE_COUNT = 3          # must have ordered at least this many times
MIN_DATE_SPAN_DAYS = 30         # must span at least 30 days of history to compute an interval
SALE_THRESHOLD = 0.95           # price must be < 95% of avg price to flag as "on sale"
PRICE_HISTORY_DAYS = 90         # rolling window for price history stored in HA
```

---

## 6. Proposed HA Entities

### Drop & Cutoff *(no auth needed)*

| Entity ID | Description |
|---|---|
| `sensor.azure_standard_next_cutoff` | Date of next order cutoff |
| `sensor.azure_standard_days_until_cutoff` | Days countdown (integer) — great for automations |
| `sensor.azure_standard_drop_name` | Your drop location name |
| `sensor.azure_standard_delivery_date` | Expected pickup/delivery date |
| `binary_sensor.azure_standard_order_window_open` | ON = order window open; OFF = past cutoff |

### Order Status *(auth required)*

| Entity ID | Description |
|---|---|
| `sensor.azure_standard_active_order_status` | `open` / `submitted` / `shipped` / `delivered` |
| `sensor.azure_standard_active_order_item_count` | Line item count in current open order |
| `sensor.azure_standard_active_order_total` | Dollar total of current open order |
| `sensor.azure_standard_last_order_date` | Date of most recently completed order |

### Shopping Lists *(auth required — dynamically created)*

One sensor per saved list:

| Entity ID | Description |
|---|---|
| `sensor.azure_standard_list_{name}_count` | Item count in list |

Attributes: `items` (array of name/code/qty), `list_uid`, `last_updated`.

### Per-Product Sensor Group *(auth required — created via discovery or manually)*

For each tracked packaging code, these sensors are created as a logical device group:

| Entity ID | Description |
|---|---|
| `sensor.azure_{product_name}_last_ordered` | Date last purchased |
| `sensor.azure_{product_name}_times_ordered` | Total lifetime purchase count |
| `sensor.azure_{product_name}_avg_order_interval` | Average days between orders |
| `sensor.azure_{product_name}_days_until_reorder` | Days until suggested reorder (negative = overdue) |
| `sensor.azure_{product_name}_current_price` | Current price from live catalogue |
| `binary_sensor.azure_{product_name}_on_sale` | ON when price is significantly below rolling average |

`on_sale` attributes: `current_price`, `average_price`, `discount_percent`, `price_history`.

### Account *(auth required)*

| Entity ID | Description |
|---|---|
| `sensor.azure_standard_account_credit` | Azure Cash / account credit balance |
| `sensor.azure_standard_pending_payment` | Outstanding payment amount |

---

## 7. Integration Architecture

### File layout

```
custom_components/azure_standard/
├── __init__.py               # async_setup_entry, async_unload_entry
├── manifest.json             # domain, version, dependencies (aiohttp built-in)
├── config_flow.py            # mode select → manual path OR account login path + options
├── const.py                  # all constants, URLs, intervals
├── api.py                    # async API client — AzureStandardApiClient
├── coordinator.py            # DataUpdateCoordinator — all polling logic
├── discovery.py              # ProductDiscoveryEngine + ProductStats dataclass
├── sensor.py                 # all sensor entities (static + dynamic product sensors)
├── binary_sensor.py          # order window + on-sale binary sensors
├── entity.py                 # AzureStandardEntity base class
├── strings.json
└── translations/en.json
```

### Coordinator polling

| Data | Interval | Auth? |
|---|---|---|
| Drop cutoff dates | 6 hours | No |
| Product prices (for on-sale) | 6 hours | No |
| Active order status | 1 hour | Yes |
| Shopping lists | 30 minutes | Yes |
| Order history + ordered products | 24 hours | Yes |
| Account credit | 24 hours | Yes |
| Session validation | 12 hours | Yes |

### Dynamic entity creation

Product sensors are created live from the options flow without requiring an HA restart. The coordinator holds a registry of `async_add_entities` callbacks per platform, and calls them when new products are confirmed.

```python
# coordinator.py
for code in self.data.newly_confirmed_products:
    self._platform_callbacks[Platform.SENSOR](
        [AzureProductSensor(self, code, stat) for stat in stats]
    )
```

### Config flow step sequence

```
async_step_user          → "Manual" or "Account login"
  ├─ async_step_manual   → enter Drop ID → create entry (mode=manual)
  └─ async_step_account  → enter email + password
        └─ validate → async_step_drop_confirm
              └─ confirm/override drop → create entry (mode=account)

OptionsFlowHandler:
  async_step_init        → credentials, drop, discovery settings
  async_step_products    → checkbox table: suggested + tracked products
```

---

## 8. Build Plan

| Phase | Work | Est. |
|---|---|---|
| 1 — Core scaffold | `manifest.json`, `const.py`, `__init__.py`, `entity.py`, `api.py` (public only), config flow mode select + manual path | 2 hr |
| 2 — Drop & cutoff sensors | Public coordinator, all 5 drop/cutoff entities, manual mode complete and working | 1.5 hr |
| 3 — Account login mode | Login flow, session cookie management, config flow account path + drop confirm step | 2 hr |
| 4 — Order sensors | Active order + history sensors | 1.5 hr |
| 5 — Shopping list sensors | Dynamic per-list sensor creation | 1 hr |
| 6 — Product discovery engine | `discovery.py` — `ProductDiscoveryEngine`, `ProductStats`, stats computation, HA repair notification | 2.5 hr |
| 7 — Product sensors | Per-product sensor group (last ordered, interval, reorder countdown, price, on-sale) | 1.5 hr |
| 8 — Options flow product management | Checkbox table UI, dynamic entity creation without restart, price history HA storage | 1.5 hr |
| 9 — Account sensors | Credit + pending payment | 0.5 hr |
| Polish | Translations, icons, README setup guide | 1 hr |

**Total: ~15 hours** for full v1.

### Automation examples unlocked

- Notify 2 days before cutoff: *"Your Azure Standard order closes in 2 days — add items now!"*
- Dashboard tile: days until pickup with green/yellow/red color coding
- On-sale alert: *"Olive Oil is 15% off this week — add it to your order!"*
- Reorder reminder: *"You're 5 days overdue to order Canned Tomatoes"*
- Shopping list alert: *"Your Staples list has 18 items — did you forget to submit your order?"*
- Order shipped notification: *"Your Azure Standard order is on the way!"*

---

## 9. Limitations & Risks

| Risk | Severity | Mitigation |
|---|---|---|
| API is undocumented and unofficial | Medium | Stable for years. Entities go `unavailable` gracefully on changes. |
| Azure Standard could add rate limiting | Medium | Conservative poll intervals well under normal browser usage. |
| Cookie auth may expire | Low | Auto re-auth; `ConfigEntryAuthFailed` triggers HA repair notification. |
| Order interval computed from aggregate, not per-order dates | Medium | `ordered-packaged-products` has `first/last-order-placed` + `quantity-ordered`. If more precision needed, `orders/orders` + `order/{id}` provide full per-order line item history. |
| Price history not stored by Azure Standard | Low | Snapshots stored locally via HA `homeassistant.helpers.storage` persistent store. On-sale detection builds its own history over time. |
| No official API terms | Medium | Mimics normal user browser behavior, single user's data, conservative polling. |

---

## Reference: washdata Patterns Applied

| washdata | Applied as |
|---|---|
| `SuggestionEngine` — learns from real cycle data | `ProductDiscoveryEngine` — learns order patterns from purchase history |
| `StatisticalModel` — rolling median/p95 per metric | `ProductStats` — rolling avg, median, price history per product |
| `MIN_SUGGESTION_COOLDOWN_CYCLES` / `MIN_SUGGESTION_REL_DELTA` | `MIN_PURCHASE_COUNT` / `MIN_DATE_SPAN_DAYS` — evidence bars before proposing |
| Clean-cycle guards (`_CLEAN_MIN_DURATION_S`, etc.) | Clean-product guards — filter products with only 1 purchase or very old data |
| `OptionsFlowHandler` — structural tuning separate from main panel | Options "Manage Products" — product checkbox table separate from initial setup |
| `profile_store.py` persistent JSON | HA `Store` (`homeassistant.helpers.storage`) for price history + discovery state |
