# Azure Standard — Home Assistant Integration Proposal

**Version:** 0.1 — August 2025  
**Status:** Draft / Pre-development

---

## Table of Contents

1. [API Findings](#1-api-findings)
2. [Authentication Model](#2-authentication-model)
3. [Confirmed Endpoints](#3-confirmed-endpoints)
4. [Proposed HA Entities](#4-proposed-ha-entities)
5. [Integration Architecture](#5-integration-architecture)
6. [Build Plan](#6-build-plan)
7. [Limitations & Risks](#7-limitations--risks)

---

## 1. API Findings

Azure Standard does not publish a public API, but their website is a JavaScript SPA (AngularJS) that consumes a REST API at `https://api.azurestandard.com`. All product, drop, and scheduling data is fetched from this API. It responds to plain HTTP requests with JSON.

**Good news:** Product listings, drop locations, and upcoming cutoff date schedules are all available **without authentication**. No API key is needed for the read-only data an HA integration would primarily use.

**Auth required for:** Cart contents, shopping lists, order history, ordered products, and account details. Authentication uses **cookie-based sessions** (`withCredentials: true`), not API keys or OAuth tokens. The HA integration will need to log in with your email/password and persist the session cookie.

---

## 2. Authentication Model

From the JavaScript source, the auth flow is:

1. `POST /login` — submits `email` + `password`, receives a session cookie named `id`
2. All subsequent requests include that cookie via `withCredentials: true`
3. `GET /session` — returns current session state (used to verify login is still valid)
4. `POST /logout` — invalidates the session

The session cookie is long-lived (authenticated sessions appear similar to the 10-year anonymous cookies). In practice the HA coordinator will log in once on setup, store the cookie, and refresh it when a 401 is received.

```http
# Auth flow example
POST https://api.azurestandard.com/login
Content-Type: application/json

{ "email": "you@example.com", "password": "..." }

→ Set-Cookie: id=<session_token>; Domain=.azurestandard.com; Secure; HttpOnly

# All subsequent authenticated calls
GET https://api.azurestandard.com/ordered-packaged-products
Cookie: id=<session_token>
```

> ⚠️ Credentials will be stored in HA's secrets / config entry storage. The integration should use HA's built-in `aiohttp` `CookieJar` and store only the session token — never the raw password after initial login.

---

## 3. Confirmed Endpoints

### Public — no auth needed

| Endpoint | Description | Key Fields |
|---|---|---|
| `GET /drops` | All drop locations with upcoming order cutoff dates | `id`, `name`, `geo`, `active`, `exclusivity`, `order-frequency[].cutoff` |
| `GET /drops/{id}` | Single drop location detail | Same as above, scoped to one drop |
| `GET /products` | Product catalogue (filterable) | `categoryId`, `limit`, `offset` query params; returns packaging, price, stock, images |
| `GET /products/{id}` | Single product detail | Full packaging/stock/price detail |

### Authenticated — requires session cookie

| Endpoint | Description | Key Fields |
|---|---|---|
| `GET /session` | Current session / login verification | `person` object with email, drop assignments, issue flags |
| `GET /person/{id}` | Account profile | Addresses, drop assignment, account flags |
| `GET /ordered-packaged-products` | Products you have ordered historically | `packaging.code`, `orderRecency`, `quantity-ordered`, `last-order-placed` |
| `GET /orders/orders` | Your order history list | Order IDs, status, cutoff, trip/delivery date, totals |
| `GET /order/{id}` | Single order detail + line items | Line items, quantities, pricing, delivery status |
| `GET /products/product_lists` | Your saved shopping lists | List name, items, quantities |
| `GET /products/shop_product_lists` | Public / followed lists | Shared community lists you follow |
| `GET /account-entries` | Account financial entries (credits, invoices) | Credit balance, invoices, payments |
| `GET /accounts_receivable/spend-metrics` | Spend summary metrics | Total spend, order counts |

> The JS source also references `packaging.next-purchase-arrival` and `packaging.vendorShortedLastPurchase` fields on ordered products — these are exactly what is needed to surface "last ordered date" and expected arrival per product.

---

## 4. Proposed HA Entities

### Drop & Cutoff Sensors *(Public API — no auth needed)*

| Entity ID | Description |
|---|---|
| `sensor.azure_standard_next_cutoff` | Date of next order cutoff for your assigned drop |
| `sensor.azure_standard_days_until_cutoff` | Integer countdown (days) to next cutoff |
| `sensor.azure_standard_drop_name` | Name of your assigned drop location |
| `sensor.azure_standard_delivery_date` | Expected pickup/delivery date for the current order cycle |
| `binary_sensor.azure_standard_order_window_open` | ON when an active order cycle is open (before cutoff), OFF after |

### Order Status Sensors *(Auth Required)*

| Entity ID | Description |
|---|---|
| `sensor.azure_standard_active_order_status` | Status of your current open order (e.g. "open", "submitted", "shipped") |
| `sensor.azure_standard_active_order_item_count` | Number of line items in the current open order |
| `sensor.azure_standard_active_order_total` | Dollar total of the current open order |
| `sensor.azure_standard_last_order_date` | Date of the most recently completed order |

### Shopping List Sensors *(Auth Required)*

| Entity ID | Description |
|---|---|
| `sensor.azure_standard_list_{name}_count` | Item count in each of your saved shopping lists (one sensor per list) |
| `sensor.azure_standard_list_{name}_items` | Attribute containing full item details (name, code, qty) from each list |

### Product / Order History Sensors *(Auth Required)*

| Entity ID | Description |
|---|---|
| `sensor.azure_standard_product_{code}_last_ordered` | Date a specific product code was last ordered (configured per-product) |
| `sensor.azure_standard_product_{code}_times_ordered` | Lifetime order count for a tracked product |

### Account Sensors *(Auth Required)*

| Entity ID | Description |
|---|---|
| `sensor.azure_standard_account_credit` | Current Azure Cash / account credit balance |
| `sensor.azure_standard_pending_payment` | Outstanding payment amount, if any |

---

## 5. Integration Architecture

### File layout

```
custom_components/azure_standard/
├── __init__.py           # Setup entry point, DataUpdateCoordinator
├── manifest.json         # Domain, version, dependencies
├── config_flow.py        # UI setup: email + password + drop ID
├── const.py              # Constants, endpoint URLs, scan intervals
├── api.py                # Async API client (aiohttp, cookie auth)
├── coordinator.py        # DataUpdateCoordinator — fetches & caches all data
├── sensor.py             # All sensor entities
├── binary_sensor.py      # Order window open/closed
├── strings.json          # UI strings
└── translations/
    └── en.json
```

### Coordinator & polling strategy

| Data type | Poll interval | Requires auth |
|---|---|---|
| Drop cutoff dates | Every 6 hours | No |
| Active order status | Every 1 hour | Yes |
| Shopping lists | Every 30 minutes | Yes |
| Order history / ordered products | Every 24 hours | Yes |
| Account credit balance | Every 24 hours | Yes |
| Session validation | Every 12 hours | Yes |

### Config flow inputs

- **Email** — Azure Standard account email
- **Password** — stored encrypted in HA config entry; used only to refresh sessions
- **Drop ID** — numeric ID of your pickup drop (auto-detectable from account, or entered manually)
- **Products to track** — optional list of packaging codes you want "last ordered" sensors for

### Authentication & error handling

- On first setup: `POST /login` → persist session cookie in config entry data
- On 401 from any call: automatically re-authenticate once, then surface `ConfigEntryAuthFailed` to prompt user if still failing
- Public endpoints (drops/cutoffs) continue to work and update even if auth lapses

---

## 6. Build Plan

| Phase | Work | Effort est. |
|---|---|---|
| **Phase 1** — Core scaffold | `manifest.json`, `const.py`, `__init__.py`, basic config flow (email + drop ID), async API client for public endpoints only | ~2 hrs |
| **Phase 2** — Drop & cutoff sensors | Coordinator fetches `/drops/{id}`, creates `next_cutoff`, `days_until_cutoff`, `delivery_date`, `order_window_open` binary sensor | ~1.5 hrs |
| **Phase 3** — Auth & order sensors | Login flow, session management, active order sensors, last order date | ~2 hrs |
| **Phase 4** — Shopping lists | Fetch `/products/product_lists`, dynamically create one sensor per list | ~1.5 hrs |
| **Phase 5** — Ordered product tracking | Fetch `/ordered-packaged-products`, create configurable per-product last-ordered sensors | ~1 hr |
| **Phase 6** — Account & credit sensors | Fetch `/account-entries` and `/accounts_receivable/spend-metrics` | ~1 hr |
| **Polish** — Translations, icons, docs | Friendly entity names, icons, README with setup instructions | ~1 hr |

**Total estimated effort: ~10 hours** for a full-featured v1 integration.

### Example automation use cases unlocked

- Notify 2 days before cutoff: *"Your Azure Standard order closes in 2 days — don't forget to add items!"*
- Dashboard tile showing days until next pickup
- Alert when a shopping list exceeds a configured item count
- Reminder if a product you order regularly hasn't been ordered in 30+ days
- Notification when order status changes to "shipped"

---

## 7. Limitations & Risks

| Risk | Severity | Mitigation |
|---|---|---|
| API is undocumented and unofficial | Medium | Endpoints have been stable for years. If they break, the integration gracefully marks entities unavailable rather than crashing. |
| Azure Standard could add rate limiting | Medium | Conservative poll intervals (minimum 30 min for auth endpoints) keep request volume very low — well under normal browser usage. |
| Cookie auth may expire unexpectedly | Low | HA will automatically re-authenticate and surface a repair notification if credentials are invalid. |
| JS bundle file hashes change on deploys | None | Integration calls the API directly — it never parses the HTML or JS. API URL structure is stable. |
| No official terms covering API use | Medium | Integration mimics normal user browser behavior. No bulk scraping. One user's data only. |
