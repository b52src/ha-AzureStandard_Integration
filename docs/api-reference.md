# Azure Standard API Reference — Confirmed Findings

> **Last verified:** August 2025 against live API
>
> All entries marked ✓ have been validated with a real authenticated session.

---

## Base URLs

| Base | Used for |
|---|---|
| `https://api.azurestandard.com` | All v1 endpoints |
| `https://api.azurestandard.com/v2` | Shopping list endpoints only |

---

## Authentication ✓

```http
POST https://api.azurestandard.com/login
Content-Type: application/json

{ "username": "you@example.com", "password": "..." }
```

> ⚠️ Field is **`username`**, NOT `email` — using `email` returns HTTP 400:
> `"JSON body missing value for username"`

**Response:** Sets cookie `id=<session_token>`; Domain=`.azurestandard.com`

**Session response shape:**
```json
{ "personId": 1000000, "person": 1000000, ... }
```
> ⚠️ `"person"` is an **integer** (same as `personId`), NOT a nested object.

---

## Public Endpoints (no auth required)

### Drop Locations ✓

```http
GET /drops?limit=200&start=0
```

> ⚠️ `GET /drops/{id}` returns **404** — single-drop lookup does not work.
> Must scan the paginated list. Default limit is 25. Max limit is 250.

**Pagination:**
- `limit` — max items per page (max 250)
- `start` — zero-based offset for pagination

**Drop shape:**
```json
{
  "id": 1234,
  "name": "Example Drop",
  "geo": {...},
  "active": true,
  "order-frequency": [
    { "cutoff": "2025-09-03", "orders": 12, "homeDeliveryOrders": [] },
    { "cutoff": "2025-10-01", "orders": 11, "homeDeliveryOrders": [] }
  ],
  "order-minimum": ...,
  "address": {...},
  "timezone": "America/Chicago"
}
```

> ⚠️ `order-frequency[].cutoff` is the only date field present — **no delivery date** in this response.

---

## Authenticated Endpoints

### Session ✓

```http
GET /session
```

**Response:**
```json
{ "personId": 1000000, "person": 1000000 }
```

---

### Drop Membership ✓

```http
GET /drop-memberships?filter-person={personId}
```

**Response (list):**
```json
[
  {
    "id": 100000,
    "customer": 1000000,
    "drop": 1234,
    "active": true,
    "heavy": false,
    "notifications": { "cutoff": ["email", "sms"] },
    "created": "2021-11-02T07:20:30.768076-07:00"
  }
]
```

---

### Person Profile ✓

```http
GET /person/{personId}
```

> ⚠️ Does **not** contain `dropId` — use `/drop-memberships` for the drop.

---

### Orders ✓

```http
GET /orders?filter-person={personId}&limit=100
```

**Order shape:**
```json
{
  "id": 10000000,
  "customerId": 1000000,
  "status": "open",
  "drop": 1234,
  "trip": 10000,
  "placed": null,
  "shipped": null,
  "lastApiUpdate": "2026-08-15T15:12:23.037039",
  "checkout-payment": {
    "paid": false,
    "type": "ACH",
    "nickname": "Checking",
    "payment-method": 12345
  },
  "customer": 1000000
}
```

> ⚠️ No `cutoffDate`, `total`, or `items` in the list response.
> Confirmed status values: **`"open"`**, **`"delivered-to-drop"`**

**Single order:**
```http
GET /order/{orderId}
```

---

### Ordered Products (Purchase History) ✓

```http
GET /person/{personId}/ordered-packaged-products
```

> ⚠️ Path requires `personId`. The old `/ordered-packaged-products` (no person prefix) returns 404.

**Item shape:**
```json
{
  "code": "BK603",
  "productId": 10000,
  "orderCount": 1,
  "lastOrderInvoiceDate": "2025-04-18",
  "lastOrderId": 10000000
}
```

> ⚠️ Fields from the proposal that do NOT exist:
> `quantity-ordered`, `last-order-placed`, `first-order-placed`, `orderRecency`,
> `packaging.next-purchase-arrival`, `packaging.vendorShortedLastPurchase`

---

### Account Balance ✓

```http
GET /account-entries?filter-person={personId}&balance=true&limit=1&start=-1
```

**Response:**
```json
[
  {
    "id": 10000000,
    "person": 1000000,
    "amount": 100.00,
    "date": "2026-07-25",
    "notes": "ACH Account: (Checking)",
    "balance": 0.0
  }
]
```

> Balance field is `"balance"` (not `"runningBalance"`).
> With `start=-1` and `limit=1` the response is a single-element list;
> the entry at index 0 is the most recent.

---

### Shopping Lists ✓

**List metadata:**
```http
GET /v2/products/product_lists?customerNumber={personId}
```

Returns up to N lists, each with at minimum `id` and `name`.

**List items:**
```http
GET /v2/products/product_lists/{listId}/items
```

**Item shape (confirmed):**
```json
{
  "id": 5602519,
  "productList": 135009,
  "quantity": 1,
  "isPinned": false,
  "pieceMetaId": 16368,
  "slug": "pasta-sauce-tomato-basil-organic",
  "image": "https://media.azurestandard.com/files/...",
  "name": "Natural Value Pasta Sauce, Tomato Basil, Organic - 24 oz",
  "directReplacement": null,
  "createdAt": "2026-08-13T19:52:20.173364",
  "productCode": "GY991"
}
```

---

## Unconfirmed / Broken Endpoints

| Endpoint | Status | Notes |
|---|---|---|
| `GET /drops/{id}` | **404** | Use paginated `/drops?limit=200&start=N` instead |
| `GET /ordered-packaged-products` | **404** | Use `GET /person/{id}/ordered-packaged-products` |
| `GET /orders/orders` | **404** | Use `GET /orders?filter-person={id}` |
| `GET /products/product_lists` | **404** | Use `GET /v2/products/product_lists?customerNumber={id}` |
| `GET /accounts_receivable/spend-metrics` | **unverified** | Not yet tested |
| `GET /accounts_receivable/pending-payments-state` | **unverified** | Not yet tested |
