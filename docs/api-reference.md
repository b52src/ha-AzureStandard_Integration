# Azure Standard API Reference — Confirmed Findings

> **Last verified:** August 2025 against live API with personId=1674720, dropId=2873
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
{ "personId": 1674720, "person": 1674720, ... }
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
> Drop 2873 ("Waxahachie") is at offset ~140 in the full list.

**Pagination:**
- `limit` — max items per page (max 250)
- `start` — zero-based offset for pagination

**Drop shape:**
```json
{
  "id": 2873,
  "name": "Waxahachie",
  "geo": {...},
  "active": true,
  "order-frequency": [
    { "cutoff": "2025-09-03", "orders": 38, "homeDeliveryOrders": [] },
    { "cutoff": "2025-10-01", "orders": 37, "homeDeliveryOrders": [] }
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
{ "personId": 1674720, "person": 1674720 }
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
    "id": 775396,
    "customer": 1674720,
    "drop": 2873,
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
  "id": 17393000,
  "customerId": 1674720,
  "status": "open",
  "drop": 2873,
  "trip": 65576,
  "placed": null,
  "shipped": null,
  "lastApiUpdate": "2026-08-15T15:12:23.037039",
  "checkout-payment": {
    "paid": false,
    "type": "ACH",
    "nickname": "USAA Checking",
    "payment-method": 3469673
  },
  "customer": 1674720
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
  "productId": 28776,
  "orderCount": 1,
  "lastOrderInvoiceDate": "2025-04-18",
  "lastOrderId": 13624820
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
    "id": 33045240,
    "person": 1674720,
    "amount": 308.66,
    "date": "2026-07-25",
    "notes": "ACH Account: (USAA Checking)",
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
Confirmed to return 11 lists for personId=1674720.

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
